"""Public workflow for plotting event windows from configured DAS recordings."""

import math
import re
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values


def plot_events(
    test_ids: list[str] | None = None,
    *,
    time_window_utc: tuple[str | datetime, str | datetime] | None = None,
    event_timezone: str = "Europe/Amsterdam",
    env_file: str | Path = ".env",
    before_seconds: float = 10,
    after_seconds: float = 10,
    channels: list[int] | None = None,
    channel_range: tuple[int, int] | None = None,
    output_dir: str | Path = "outputs",
    show: bool = True,
    normalize_channels: bool = False,
    bandpass_hz: tuple[float, float] | None = None,
) -> list[Path]:
    """Save waterfall/PSD figures and return their paths.

    Event-list times use event_timezone and are converted to UTC. None for both channel selectors means all
    recorded channels. Channel ranges include both endpoints. Relative data
    paths in the environment file are resolved beside that file; output paths
    are relative to the current working directory. Invalid input or incomplete
    recordings raise an exception rather than producing a partial plot.

    time_window_utc overrides test IDs and before/after durations. Supply ISO
    timestamps or datetime objects; timestamps without an offset mean UTC.
    Manual mode does not require an event list or add measurement markers.
    normalize_channels rescales only the waterfall by each channel's 75th
    percentile absolute amplitude, floored at one count. Raw data and PSD are
    unchanged. Normalized colors use fixed limits of +/-3.
    bandpass_hz optionally filters the joined window before plotting and PSD,
    using a fourth-order Butterworth design in second-order sections with
    forward/backward zero-phase filtering. Raw source files remain unchanged.
    """
    from .plot_event import Event, extract_window, plot_window, read_events, scan_recordings

    if time_window_utc is None:
        if not test_ids or isinstance(test_ids, str) or any(not isinstance(test_id, str) or not test_id.strip() for test_id in test_ids):
            raise ValueError("test_ids must be a nonempty list of test-ID strings")
        if not all(math.isfinite(value) and value >= 0 for value in (before_seconds, after_seconds)):
            raise ValueError("before_seconds/after_seconds must be finite and nonnegative")
    if channels is not None and channel_range is not None:
        raise ValueError("Choose channels or channel_range, not both")
    if channel_range is not None and (len(channel_range) != 2 or channel_range[0] > channel_range[1]):
        raise ValueError("channel_range must contain MIN and MAX with MIN <= MAX")

    env_path = Path(env_file).resolve()
    config = dotenv_values(env_path)

    def configured_path(key: str) -> Path:
        value = config.get(key)
        if not value:
            raise ValueError(f"Missing {key} in {env_path}")
        path = Path(value)
        return path if path.is_absolute() else env_path.parent / path

    if time_window_utc is not None:
        if isinstance(time_window_utc, str) or len(time_window_utc) != 2:
            raise ValueError("time_window_utc must contain a start and end timestamp")

        def utc_timestamp(value: str | datetime) -> datetime:
            if isinstance(value, str):
                value = datetime.fromisoformat(value)
            if not isinstance(value, datetime):
                raise ValueError("Manual timestamps must be ISO strings or datetime objects")
            return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

        start, end = (utc_timestamp(value) for value in time_window_utc)
        if end <= start:
            raise ValueError("Manual window end must be later than its start")
        events = [Event("Manual window", [], start, end)]
    else:
        events = read_events(configured_path("event_list"), test_ids, before_seconds, after_seconds, event_timezone=event_timezone)
    recordings = scan_recordings(configured_path("data_folder"), skip_unreadable=True)
    print(f"Indexed {len(recordings)} recording headers")
    outputs = []
    for event in events:
        window = extract_window(recordings, event, channels, channel_range)
        print(f"{event.test_id}: {event.start.isoformat()} to {event.end.isoformat()}, {window.counts.shape}, {1 / window.dt:g} Hz")
        for source in window.sources:
            print(f"  {source.name}")
        name = re.sub(r"[^A-Za-z0-9_-]", "_", event.test_id)
        if time_window_utc is not None:
            name = f"manual_{event.start:%Y%m%dT%H%M%S%f}_{event.end:%Y%m%dT%H%M%S%f}"
        output = Path(output_dir).resolve() / f"{name}_waterfall_psd.png"
        plot_window(event, window, output, show, normalize_channels=normalize_channels, bandpass_hz=bandpass_hz)
        outputs.append(output)
    return outputs