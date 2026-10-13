"""Read UTC event windows from OptoDAS files and plot waterfall and Welch PSD."""

import argparse
import csv
import math
import re
import warnings
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import h5py
import numpy as np
from scipy.signal import butter, sosfiltfilt, welch


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Event:
    test_id: str
    measurements: list[datetime]
    start: datetime
    end: datetime


@dataclass
class Recording:
    path: Path
    start: float
    end: float
    dt: float


@dataclass
class Window:
    counts: np.ndarray
    timestamps: np.ndarray
    channels: np.ndarray
    distances: np.ndarray
    dt: float
    sources: list[Path]


def normalize_id(value: str) -> str:
    compact = re.sub(r"[-\s_]", "", value).upper()
    match = re.fullmatch(r"([A-Z]+)(\d+)", compact)
    return f"{match[1]}{int(match[2])}" if match else compact


def read_events(path: Path, test_ids: list[str], before: float, after: float, *, event_timezone: str = "UTC") -> list[Event]:
    source_timezone = ZoneInfo(event_timezone)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    events = []
    for test_id in dict.fromkeys(test_ids):
        matches = [row for row in rows if normalize_id(row["Test-ID"]) == normalize_id(test_id)]
        if len(matches) != 1:
            raise ValueError(f"Expected one CSV row for {test_id}, found {len(matches)}")
        row = matches[0]
        date = None
        for date_format in ("%Y-%m-%d", "%d-%m-%Y"):
            try:
                date = datetime.strptime(row["Date"].strip(), date_format).date()
                break
            except ValueError:
                pass
        if date is None:
            raise ValueError(f"Invalid Date for {test_id}: {row['Date']!r}")
        measurements = []
        for column in ("1e meting", "2e meting"):
            value = row[column].strip()
            if value:
                clock = datetime.strptime(value, "%H:%M:%S").time()
                measurements.append(datetime.combine(date, clock, tzinfo=source_timezone).astimezone(timezone.utc))
        if not measurements:
            raise ValueError(f"No actual measurement times for {test_id}")
        events.append(Event(
            row["Test-ID"], measurements,
            min(measurements) - timedelta(seconds=before),
            max(measurements) + timedelta(seconds=after),
        ))
        if events[-1].end <= events[-1].start:
            raise ValueError(f"Empty time window for {test_id}; increase before/after")
    return events


def scan_recordings(folder: Path, *, skip_unreadable: bool = False) -> list[Recording]:
    if not folder.is_dir():
        raise ValueError(f"Data folder does not exist: {folder}")
    recordings = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".h5", ".hdf5", ".hdf"}:
            continue
        try:
            with h5py.File(path, "r") as handle:
                shape = handle["data"].shape
                start = float(handle["header/time"][()])
                dt = float(handle["header/dt"][()])
                if len(shape) != 2 or shape[0] == 0 or not math.isfinite(start) or not math.isfinite(dt) or dt <= 0:
                    raise ValueError("Invalid data shape or sampling metadata")
                recordings.append(Recording(path, start, start + shape[0] * dt, dt))
        except (OSError, KeyError, ValueError) as error:
            if not skip_unreadable:
                raise ValueError(f"Cannot index {path}: {error}") from error
            warnings.warn(f"Skipping unreadable recording {path}: {error}", RuntimeWarning, stacklevel=2)
    if not recordings:
        raise ValueError(f"No readable HDF5 recordings found in {folder}")
    return sorted(recordings, key=lambda recording: recording.start)


def extract_window(
    recordings: list[Recording], event: Event,
    channels: list[int] | None = None, channel_range: list[int] | None = None,
) -> Window:
    start, end = event.start.timestamp(), event.end.timestamp()
    selected = [recording for recording in recordings if recording.start < end and recording.end > start]
    if not selected:
        raise ValueError(f"No recordings overlap {event.test_id}: {event.start.isoformat()} to {event.end.isoformat()}")
    blocks, times, sources = [], [], []
    reference_channels = reference_distances = columns = None
    dt = selected[0].dt
    previous_end = None
    for recording in selected:
        if not math.isclose(recording.dt, dt, rel_tol=1e-9, abs_tol=1e-12):
            raise ValueError(f"Sample interval changed in {recording.path}")
        with h5py.File(recording.path, "r") as handle:
            data = handle["data"]
            file_channels = handle["header/channels"][:]
            distances = handle["cableSpec/sensorDistances"][:]
            if len(file_channels) != data.shape[1] or distances.shape != file_channels.shape:
                raise ValueError(f"Invalid spatial metadata in {recording.path}")
            if len(np.unique(file_channels)) != len(file_channels) or not np.all(np.isfinite(distances)) or np.any(np.diff(distances) <= 0):
                raise ValueError(f"Non-unique channels or non-increasing distances in {recording.path}")
            if handle["header/missingSamples"].size:
                raise ValueError(f"Missing samples declared in {recording.path}; cannot treat data as continuous")
            if reference_channels is None:
                reference_channels, reference_distances = file_channels, distances
                mask = np.ones(len(file_channels), dtype=bool)
                if channels is not None:
                    missing = sorted(set(channels) - set(file_channels.tolist()))
                    if missing:
                        raise ValueError(f"Channel IDs not recorded: {missing}")
                    mask = np.isin(file_channels, channels)
                if channel_range is not None:
                    mask = (file_channels >= channel_range[0]) & (file_channels <= channel_range[1])
                columns = np.flatnonzero(mask)
                if not len(columns):
                    raise ValueError("Channel selection is empty")
            elif not np.array_equal(file_channels, reference_channels) or not np.allclose(distances, reference_distances, rtol=0, atol=1e-8):
                raise ValueError(f"Channel/distance mapping changed in {recording.path}")
            first = max(0, math.ceil((start - recording.start) / dt - 0.001))
            stop = min(data.shape[0], math.ceil((end - recording.start) / dt - 0.001))
            if stop <= first:
                continue
            block_start = recording.start + first * dt
            if previous_end is not None and abs(block_start - previous_end) > dt * 0.01:
                raise ValueError(f"Gap or overlap before {recording.path}; refusing a misleading plot/PSD")
            if len(columns) == data.shape[1]:
                block = data[first:stop, :]
            elif np.all(np.diff(columns) == 1):
                block = data[first:stop, columns[0]:columns[-1] + 1]
            else:
                block = data[first:stop, columns]
            blocks.append(block)
            times.append(recording.start + np.arange(first, stop) * dt)
            sources.append(recording.path)
            previous_end = recording.start + stop * dt
    if not blocks:
        raise ValueError("Requested window contains no samples")
    timestamps = np.concatenate(times)
    if timestamps[0] - start > dt * 1.01 or end - (timestamps[-1] + dt) > dt * 0.01:
        raise ValueError("Recordings do not cover the complete requested window")
    return Window(np.concatenate(blocks), timestamps, reference_channels[columns], reference_distances[columns], dt, sources)


def mean_psd(window: Window) -> tuple[np.ndarray, np.ndarray]:
    if len(window.counts) < 2:
        raise ValueError("PSD needs at least two samples")
    frequencies, power = welch(
        window.counts.astype(np.float32), fs=1 / window.dt,
        window="hann", nperseg=min(len(window.counts), max(2, round(2 / window.dt))),
        detrend=False, axis=0, scaling="density",
    )
    return frequencies, power.mean(axis=1)


def bandpass_window(window: Window, bandpass_hz: tuple[float, float] | None) -> Window:
    """Filter the continuous time axis without modifying extracted raw counts."""
    if bandpass_hz is None:
        return window
    if len(bandpass_hz) != 2 or not all(math.isfinite(value) for value in bandpass_hz):
        raise ValueError("bandpass_hz must contain two finite frequencies")
    low, high = bandpass_hz
    if not 0 < low < high < 0.5 / window.dt:
        raise ValueError(f"Bandpass requires 0 < LOW < HIGH < Nyquist ({0.5 / window.dt:g} Hz)")
    sections = butter(4, (low, high), btype="bandpass", fs=1 / window.dt, output="sos")
    try:
        filtered = sosfiltfilt(sections, window.counts.astype(np.float64), axis=0)
    except ValueError as error:
        raise ValueError("Time window is too short for bandpass filtering; increase its duration") from error
    return Window(filtered, window.timestamps, window.channels, window.distances, window.dt, window.sources)


def waterfall_display(counts: np.ndarray, normalize_channels: bool = False) -> tuple[np.ndarray, float, str]:
    """Prepare waterfall colors without modifying the samples used for the PSD."""
    values = counts.astype(np.float32)
    if normalize_channels:
        scales = np.maximum(np.percentile(np.abs(values), 75, axis=0), 1)
        return values / scales, 3.0, "Per-channel normalized counts (75th-percentile scale; limits +/-3)"
    limit = max(1.0, float(np.percentile(np.abs(values), 99)))
    return counts, limit, "Raw counts (color limits: 99th percentile)"


def plot_window(
    event: Event, window: Window, output: Path, show: bool, *,
    normalize_channels: bool = False, bandpass_hz: tuple[float, float] | None = None,
) -> None:
    import matplotlib

    if not show:
        matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    from matplotlib.colors import TwoSlopeNorm

    window = bandpass_window(window, bandpass_hz)
    processing_label = "" if bandpass_hz is None else f"\nBandpass {bandpass_hz[0]:g}-{bandpass_hz[1]:g} Hz (zero phase)"
    frequencies, power = mean_psd(window)
    figure, (waterfall, spectrum) = plt.subplots(
        1, 2, figsize=(16, 8), gridspec_kw={"width_ratios": [2.2, 1]}, layout="constrained",
    )
    time_edges = mdates.date2num(
        [datetime.fromtimestamp(timestamp, timezone.utc) for timestamp in (window.timestamps[0], window.timestamps[-1] + window.dt)]
    )
    display, limit, color_label = waterfall_display(window.counts, normalize_channels)
    if bandpass_hz is not None:
        color_label = color_label.replace("Raw counts", "Bandpassed counts")
    if len(window.distances) > 1:
        edges = np.r_[window.distances[0] - (window.distances[1] - window.distances[0]) / 2,
                      (window.distances[:-1] + window.distances[1:]) / 2,
                      window.distances[-1] + (window.distances[-1] - window.distances[-2]) / 2]
    else:
        edges = np.array([window.distances[0] - 0.5, window.distances[0] + 0.5])
    image = waterfall.pcolormesh(
        edges, np.linspace(*time_edges, len(window.counts) + 1), display,
        cmap="RdBu_r", norm=TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit), rasterized=True,
    )
    waterfall.invert_yaxis()
    waterfall.yaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S", tz=timezone.utc))
    waterfall.yaxis.set_major_locator(mdates.AutoDateLocator())
    waterfall.set(xlabel="Fiber distance (m)", ylabel="Time (UTC)", title=f"{event.test_id} | {event.start:%Y-%m-%d} | {len(window.channels)} channels{processing_label}")
    for number, measurement in enumerate(event.measurements, 1):
        waterfall.axhline(mdates.date2num(measurement), color="#202020", linestyle="--", linewidth=1, label=f"Measurement {number}: {measurement:%H:%M:%S}")
    if event.measurements:
        waterfall.legend(loc="upper right", fontsize=8)
    figure.colorbar(image, ax=waterfall, label=color_label, extend="both")
    positive = frequencies > 0
    spectrum.semilogy(frequencies[positive], np.maximum(power[positive], np.finfo(np.float32).tiny), color="#16645c")
    spectrum.set(xlabel="Frequency (Hz)", ylabel="PSD (counts squared/Hz)", title=f"Mean per-channel Welch PSD{processing_label}", xlim=(0, 0.5 / window.dt))
    spectrum.grid(True, alpha=0.25)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=160)
    print(f"Saved {output.resolve()}")
    if show:
        plt.show()
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test-ids", nargs="+", default=["IJK-027"])
    parser.add_argument("--event-timezone", default="Europe/Amsterdam", help="Timezone of event-list clock times")
    parser.add_argument("--time-window-utc", nargs=2, metavar=("START", "END"), help="Exact ISO UTC window; overrides IDs and before/after durations")
    parser.add_argument("--env", type=Path, default=PROJECT_ROOT / ".env")
    parser.add_argument("--before", type=float, default=10, help="Seconds before the first actual measurement")
    parser.add_argument("--after", type=float, default=10, help="Seconds after the last actual measurement")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--channels", nargs="+", type=int, help="Recorded channel IDs, not column indices")
    selection.add_argument("--channel-range", nargs=2, type=int, metavar=("MIN", "MAX"), help="Inclusive channel-ID interval")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "outputs")
    parser.add_argument("--normalize-channels", action="store_true", help="Normalize each waterfall channel for display only; PSD is unchanged")
    parser.add_argument("--bandpass-hz", nargs=2, type=float, metavar=("LOW", "HIGH"), help="Zero-phase bandpass in Hz, applied to the waterfall and PSD")
    parser.add_argument("--no-show", action="store_true", help="Save PNG without opening a plot window")
    args = parser.parse_args()
    if args.time_window_utc is None and not all(math.isfinite(value) and value >= 0 for value in (args.before, args.after)):
        parser.error("before/after must be finite and nonnegative")
    if args.channel_range and args.channel_range[0] > args.channel_range[1]:
        parser.error("channel-range MIN must not exceed MAX")
    try:
        from .workflow import plot_events

        plot_events(
            args.test_ids,
            event_timezone=args.event_timezone,
            time_window_utc=tuple(args.time_window_utc) if args.time_window_utc else None,
            env_file=args.env,
            before_seconds=args.before,
            after_seconds=args.after,
            channels=args.channels,
            channel_range=tuple(args.channel_range) if args.channel_range else None,
            output_dir=args.output_dir,
            normalize_channels=args.normalize_channels,
            bandpass_hz=tuple(args.bandpass_hz) if args.bandpass_hz else None,
            show=not args.no_show,
        )
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()