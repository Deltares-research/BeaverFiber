"""Map view of the DAS amplitudes along the fiber, per time slice: QGIS GeoPackage and MP4."""

import re
from datetime import timedelta
from pathlib import Path

from .fiber_map import load_fiber_map, upsample_fiber
from .plot_event import (
    color_limit, extract_window, normalize, process_counts, read_events, scan_recordings,
)
from .time_slices import layer_name, select_slices, write_time_slices


def make_event_movies(
    test_ids: list[str], *, measurements: list[str], time_delta: timedelta,
    noise_seconds: float, signal_seconds: float, fiber_range_m: tuple[float, float] | None,
    normalize_channels: bool, bandpass_hz: tuple[float, float] | None, envelope: bool,
    clip_quantile: float, slice_interval_s: float, upsample_factor: int,
    data_folder: str | Path, event_list: str | Path, fiber_map: str | Path, output_dir: str | Path,
    write_geopackage: bool, write_mp4: bool, frame_rate: float, basemap: str | None,
    waterfall_inset: bool, map_extent_rd: tuple[float, float, float, float] | None, line_width: float,
) -> None:
    """Per test and measurement: process like view_events, take time slices, upsample along the cable, save."""
    import matplotlib

    matplotlib.use("Agg")
    if not (write_geopackage or write_mp4):
        raise ValueError("Set WRITE_GEOPACKAGE and/or WRITE_MP4 to True")
    if slice_interval_s <= 0 or frame_rate <= 0:
        raise ValueError("SLICE_INTERVAL_S and FRAME_RATE must be positive")
    output_dir = Path(output_dir)
    geopackage = output_dir / f"{Path(data_folder).name}_time_slices.gpkg"
    cable = load_fiber_map(fiber_map)
    events = read_events(Path(event_list), test_ids, measurements, noise_seconds, signal_seconds, time_delta)
    recordings = scan_recordings(Path(data_folder))

    for event in events:
        window = extract_window(recordings, event.start.timestamp(), event.end.timestamp(), fiber_range_m)
        counts = process_counts(window, bandpass_hz, envelope)
        if normalize_channels:
            counts = normalize(counts)
        slices, times, interval = select_slices(counts, window.timestamps, window.dt, slice_interval_s)
        fiber = upsample_fiber(cable, window.channels, window.distances, upsample_factor)
        values = fiber.interpolate(slices)
        limit = color_limit(values, clip_quantile)
        event_time = event.time.timestamp()
        filtered = "" if bandpass_hz is None else f" | bandpass {bandpass_hz[0]:g}-{bandpass_hz[1]:g} Hz"
        title = (f"{event.test_id} | {event.measurement} | {event.time:%Y-%m-%d %H:%M:%S} UTC{filtered}"
                 f"{' | envelope' if envelope else ''}{' | normalized' if normalize_channels else ''}")
        print(f"{event.test_id} | {event.measurement}: {len(times)} slices of {interval * 1000:g} ms, "
              f"{len(fiber.channel)} map points ({len(fiber.columns)} channels x{upsample_factor})")

        if write_geopackage:
            write_time_slices(
                geopackage, layer_name(event.test_id, event.measurement), cable, fiber, values, times,
                interval, event_time, envelope, limit, title,
            )
        if write_mp4:
            from .movie import write_movie

            name = re.sub(r"[^A-Za-z0-9_-]", "_", f"{event.test_id}_{event.measurement}")
            write_movie(
                output_dir / f"{name}_time_slices.mp4", cable, fiber, values, times,
                slices[:, fiber.columns], window.distances[fiber.columns], event_time, title=title,
                envelope=envelope, limit=limit, frame_rate=frame_rate, basemap=basemap,
                waterfall_inset=waterfall_inset, map_extent_rd=map_extent_rd, line_width=line_width,
            )
