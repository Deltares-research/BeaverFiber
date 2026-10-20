"""Plot a waterfall and noise/signal PSD around measurements from the event list."""

import csv
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import h5py
import numpy as np
from dotenv import dotenv_values
from scipy.signal import butter, sosfiltfilt, welch


@dataclass
class Event:
    test_id: str
    measurement: str
    time: datetime
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


def env_path(env_file: str | Path, key: str) -> Path:
    """Read a path from .env; relative paths are relative to the .env file."""
    env_file = Path(env_file).resolve()
    value = dotenv_values(env_file).get(key)
    if not value:
        raise ValueError(f"Missing {key} in {env_file}")
    return env_file.parent / value


def normalize_id(value: str) -> str:
    """Make IJK-001, IJK1 and ijk 001 equal."""
    compact = re.sub(r"[-\s_]", "", value).upper()
    match = re.fullmatch(r"([A-Z]+)(\d+)", compact)
    return f"{match[1]}{int(match[2])}" if match else compact


def read_events(
    path: Path, test_ids: list[str], measurement: str,
    noise_seconds: float, signal_seconds: float, time_delta: timedelta,
) -> list[Event]:
    if measurement not in ("1e meting", "2e meting"):
        raise ValueError('MEASUREMENT must be "1e meting" or "2e meting"')
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = {normalize_id(row["Test-ID"]): row for row in csv.DictReader(stream)}
    events = []
    for test_id in test_ids:
        row = rows.get(normalize_id(test_id))
        if row is None:
            raise ValueError(f"{test_id} is not in the event list")
        value = row[measurement].strip()
        try:
            date = row["Date"].strip()
            date_format = "%d-%m-%Y" if date[2] == "-" else "%Y-%m-%d"
            clock = datetime.strptime(f"{date} {value}", f"{date_format} %H:%M:%S")
        except (ValueError, IndexError) as error:
            raise ValueError(f"No valid {measurement} time for {test_id}: {value!r}") from error
        time = clock.replace(tzinfo=timezone.utc) - time_delta
        events.append(Event(
            row["Test-ID"], measurement, time,
            time - timedelta(seconds=noise_seconds), time + timedelta(seconds=signal_seconds),
        ))
    return events


def scan_recordings(folder: Path) -> list[Recording]:
    recordings = []
    for path in sorted(folder.rglob("*.hdf5")):
        try:
            with h5py.File(path, "r") as handle:
                start = float(handle["header/time"][()])
                dt = float(handle["header/dt"][()])
                recordings.append(Recording(path, start, start + handle["data"].shape[0] * dt, dt))
        except (OSError, KeyError) as error:
            print(f"Skipping unreadable recording {path.name}: {error}")
    if not recordings:
        raise ValueError(f"No readable .hdf5 recordings found in {folder}")
    return sorted(recordings, key=lambda recording: recording.start)


def extract_window(
    recordings: list[Recording], start: float, end: float,
    fiber_range_m: tuple[float, float] | None,
) -> Window:
    """Join samples between UTC timestamps start (inclusive) and end (exclusive); refuse gaps."""
    blocks, times = [], []
    channels = distances = columns = previous_end = None
    for recording in recordings:
        if recording.end <= start or recording.start >= end:
            continue
        dt = recording.dt
        with h5py.File(recording.path, "r") as handle:
            if columns is None:
                channels = handle["header/channels"][:]
                distances = handle["cableSpec/sensorDistances"][:]
                low, high = fiber_range_m or (-math.inf, math.inf)
                columns = np.flatnonzero((distances >= low) & (distances <= high))
                if not len(columns):
                    raise ValueError(f"FIBER_RANGE_M {fiber_range_m} contains no channels")
            first = max(0, math.ceil((start - recording.start) / dt - 0.001))
            stop = min(handle["data"].shape[0], math.ceil((end - recording.start) / dt - 0.001))
            if stop <= first:
                continue
            block_start = recording.start + first * dt
            if previous_end is not None and abs(block_start - previous_end) > dt * 0.01:
                raise ValueError(f"Gap in recordings before {recording.path.name}")
            blocks.append(handle["data"][first:stop, columns[0]:columns[-1] + 1])
            times.append(block_start + np.arange(stop - first) * dt)
            previous_end = recording.start + stop * dt
    if not blocks:
        raise ValueError("No recordings cover the requested time")
    timestamps = np.concatenate(times)
    if timestamps[0] - start > dt * 1.01 or end - previous_end > dt * 0.01:
        raise ValueError("Recordings do not cover the complete requested time")
    return Window(np.concatenate(blocks), timestamps, channels[columns], distances[columns], dt)


def bandpass(counts: np.ndarray, dt: float, bandpass_hz: tuple[float, float]) -> np.ndarray:
    """Zero-phase 4th-order Butterworth bandpass along time."""
    if not 0 < bandpass_hz[0] < bandpass_hz[1] < 0.5 / dt:
        raise ValueError(f"BANDPASS_HZ must satisfy 0 < LOW < HIGH < {0.5 / dt:g} Hz")
    sections = butter(4, bandpass_hz, btype="bandpass", fs=1 / dt, output="sos")
    return sosfiltfilt(sections, counts.astype(np.float64), axis=0)


def mean_psd(counts: np.ndarray, dt: float) -> tuple[np.ndarray, np.ndarray]:
    """Welch PSD averaged over channels."""
    if len(counts) < 2:
        raise ValueError("Noise and signal windows need at least two samples each")
    frequencies, power = welch(
        counts.astype(np.float32), fs=1 / dt, nperseg=min(len(counts), round(2 / dt)),
        detrend=False, axis=0,
    )
    return frequencies, power.mean(axis=1)


def color_limit(values: np.ndarray, clip_quantile: float) -> float:
    """Symmetric color limit; clip_quantile 1.0 shows the full amplitude range."""
    if not 0 < clip_quantile <= 1:
        raise ValueError("CLIP_QUANTILE must be larger than 0 and at most 1")
    return max(float(np.quantile(np.abs(values), clip_quantile)), 1e-12)


def normalize(values: np.ndarray) -> np.ndarray:
    """Scale each channel by its 75th-percentile absolute amplitude."""
    return values / np.maximum(np.percentile(np.abs(values), 75, axis=0), 1)


def waterfall_image(axes, distances: np.ndarray, values: np.ndarray, time_bounds, interpolation: str, **kwargs):
    spacing = (distances[-1] - distances[0]) / (len(distances) - 1) if len(distances) > 1 else 1.0
    extent = (distances[0] - spacing / 2, distances[-1] + spacing / 2, *time_bounds)
    return axes.imshow(values, extent=extent, origin="lower", aspect="auto", interpolation=interpolation, **kwargs)


def plot_window(
    event: Event, window: Window, output: Path, *, show: bool, normalize_channels: bool,
    bandpass_hz: tuple[float, float] | None, interpolation: str, clip_quantile: float,
    write_segy: bool,
) -> None:
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    counts = window.counts if bandpass_hz is None else bandpass(window.counts, window.dt, bandpass_hz)
    if write_segy:
        from .segy_export import write_segy as write

        write(event, window, counts, output.with_suffix(".sgy"))

    figure, (waterfall, spectrum) = plt.subplots(
        1, 2, figsize=(16, 8), gridspec_kw={"width_ratios": [2.2, 1]}, layout="constrained",
    )
    display = normalize(counts) if normalize_channels else counts
    limit = color_limit(display, clip_quantile)
    times = [datetime.fromtimestamp(t, timezone.utc) for t in (window.timestamps[0], window.timestamps[-1] + window.dt)]
    image = waterfall_image(
        waterfall, window.distances, display, mdates.date2num(times), interpolation,
        cmap="RdBu_r", vmin=-limit, vmax=limit,
    )
    waterfall.invert_yaxis()
    waterfall.yaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S", tz=timezone.utc))
    waterfall.axhline(mdates.date2num(event.time), color="k", linestyle="--", linewidth=1,
                      label=f"{event.measurement}: {event.time:%H:%M:%S} UTC")
    waterfall.legend(loc="upper right")
    filtered = "" if bandpass_hz is None else f" | bandpass {bandpass_hz[0]:g}-{bandpass_hz[1]:g} Hz"
    waterfall.set(
        xlabel="Fiber distance (m)", ylabel="Time (UTC)",
        title=f"{event.test_id} | {event.measurement} | {event.time:%Y-%m-%d}{filtered}",
    )
    label = "Normalized counts" if normalize_channels else "Counts"
    figure.colorbar(image, ax=waterfall, label=f"{label} (clip quantile {clip_quantile:g})", extend="both")

    split = int(np.searchsorted(window.timestamps, event.time.timestamp()))
    for name, part, color in (("Noise", counts[:split], "#737373"), ("Signal", counts[split:], "#16645c")):
        frequencies, power = mean_psd(part, window.dt)
        spectrum.semilogy(frequencies[1:], power[1:], color=color, label=name)
    spectrum.legend()
    spectrum.grid(True, alpha=0.25)
    spectrum.set(xlabel="Frequency (Hz)", ylabel="PSD (counts²/Hz)", title=f"Mean Welch PSD over channels{filtered}")

    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=160)
    print(f"Saved {output}")
    if show:
        plt.show()
    plt.close(figure)


def plot_events(
    test_ids: list[str], *, measurement: str, time_delta: timedelta,
    noise_seconds: float, signal_seconds: float, fiber_range_m: tuple[float, float] | None,
    normalize_channels: bool, bandpass_hz: tuple[float, float] | None,
    interpolation: str, clip_quantile: float, env_file: str | Path, output_dir: str | Path,
    show: bool, write_segy: bool,
) -> None:
    """Save one waterfall/PSD figure (and optionally a SEG-Y file) per test ID."""
    if not show:
        import matplotlib

        matplotlib.use("Agg")
    events = read_events(env_path(env_file, "event_list"), test_ids, measurement, noise_seconds, signal_seconds, time_delta)
    recordings = scan_recordings(env_path(env_file, "data_folder"))
    for event in events:
        window = extract_window(recordings, event.start.timestamp(), event.end.timestamp(), fiber_range_m)
        print(f"{event.test_id} | {measurement}: {event.start:%H:%M:%S.%f} to {event.end:%H:%M:%S.%f} UTC, "
              f"fiber {window.distances[0]:.1f}-{window.distances[-1]:.1f} m ({len(window.channels)} channels)")
        name = f"{re.sub(r'[^A-Za-z0-9_-]', '_', event.test_id)}_{measurement.replace(' ', '_')}_waterfall_psd.png"
        plot_window(
            event, window, Path(output_dir) / name, show=show, normalize_channels=normalize_channels,
            bandpass_hz=bandpass_hz, interpolation=interpolation, clip_quantile=clip_quantile,
            write_segy=write_segy,
        )
