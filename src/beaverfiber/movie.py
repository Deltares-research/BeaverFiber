"""Render the time slices as an MP4 map movie."""

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .fiber_map import FiberMap, UpsampledFiber
from .plot_event import waterfall_image


def _import_contextily():
    # Other programs on PATH (e.g. ParaView, QGIS) can ship their own gdal.dll, which then breaks rasterio
    # with "DLL load failed ... procedure could not be found". Loading the environment's GDAL first avoids that.
    gdal_dll = Path(sys.prefix) / "Library" / "bin" / "gdal.dll"
    if sys.platform == "win32" and gdal_dll.exists():
        import ctypes
        try:
            ctypes.WinDLL(str(gdal_dll), winmode=0x8)  # LOAD_WITH_ALTERED_SEARCH_PATH
        except OSError:
            pass
    try:
        import contextily
    except ImportError as error:
        raise RuntimeError(
            f"Could not load contextily for BASEMAP ({error}). Run 'pixi install', or set BASEMAP = None."
        ) from error
    return contextily


def write_movie(
    path: Path, fiber_map: FiberMap, fiber: UpsampledFiber, values: np.ndarray, times: np.ndarray,
    waterfall: np.ndarray, waterfall_distances: np.ndarray, event_time: float, *, title: str,
    envelope: bool, limit: float, frame_rate: float, basemap: str | None, waterfall_inset: bool,
    map_extent_rd: tuple[float, float, float, float] | None, line_width: float, dpi: int = 120,
) -> None:
    import matplotlib
    import matplotlib.pyplot as plt
    from matplotlib import animation
    from matplotlib.collections import LineCollection

    if not animation.writers.is_available("ffmpeg"):
        raise RuntimeError("ffmpeg was not found. Run 'pixi install' to install it, or set WRITE_MP4 = False.")

    relative = times - event_time
    figure = plt.figure(figsize=(16, 9) if waterfall_inset else (11, 9), dpi=dpi, layout="constrained")
    if waterfall_inset:
        map_axes, time_axes = figure.subplots(1, 2, gridspec_kw={"width_ratios": [2.2, 1]})
    else:
        map_axes, time_axes = figure.subplots(), None

    style = {"cmap": "viridis", "vmin": 0, "vmax": limit} if envelope else {"cmap": "RdBu_r", "vmin": -limit, "vmax": limit}
    map_axes.plot(*fiber_map.line.T, color="0.6", linewidth=0.8, zorder=1)
    cable = LineCollection(fiber.segments, linewidths=line_width, capstyle="butt", zorder=2,
                           cmap=style["cmap"])
    cable.set_clim(style["vmin"], style["vmax"])
    cable.set_array(values[0])
    map_axes.add_collection(cable)
    if map_extent_rd is None:
        low, high = fiber.segments.reshape(-1, 2).min(axis=0), fiber.segments.reshape(-1, 2).max(axis=0)
        margin = 0.05 * (high - low).max()
        map_extent_rd = (low[0] - margin, high[0] + margin, low[1] - margin, high[1] + margin)
    map_axes.set_xlim(map_extent_rd[:2])
    map_axes.set_ylim(map_extent_rd[2:])
    map_axes.set_aspect("equal")
    map_axes.set(xlabel="RD x (m)", ylabel="RD y (m)")
    map_axes.ticklabel_format(useOffset=False, style="plain")
    if basemap:
        contextily = _import_contextily()
        contextily.add_basemap(map_axes, crs=f"EPSG:{int(fiber_map.srs[3])}",
                               source=contextily.providers.query_name(basemap), attribution_size=6)
    label = "Envelope (counts)" if envelope else "Amplitude (counts)"
    figure.colorbar(cable, ax=map_axes, label=label, shrink=0.8, extend="max" if envelope else "both")
    clock = map_axes.set_title("")

    cursor = None
    if time_axes is not None:
        step = times[1] - times[0] if len(times) > 1 else 1.0
        waterfall_image(time_axes, waterfall_distances, waterfall, (relative[0], relative[-1] + step), "nearest",
                        **style)
        time_axes.invert_yaxis()
        time_axes.axhline(0, color="k", linestyle="--", linewidth=1)
        cursor = time_axes.axhline(relative[0], color="orange", linewidth=2)
        time_axes.set(xlabel="Fiber distance (m)", ylabel="Time since event start (s)")

    figure.suptitle(title)

    def draw(frame: int):
        cable.set_array(values[frame])
        phase = "noise (before event)" if relative[frame] < 0 else "event"
        utc = datetime.fromtimestamp(times[frame], timezone.utc)
        clock.set_text(f"t = {relative[frame]:+.3f} s  |  {phase}  |  {utc:%H:%M:%S.%f}"[:-3] + " UTC")
        if cursor is not None:
            cursor.set_ydata([relative[frame]] * 2)
    # Draw the static parts (basemap, waterfall, axes) once; per frame, only redraw what changes.
    moving = [artist for artist in (cable, clock, cursor) if artist is not None]
    for artist in moving:
        artist.set_animated(True)
    figure.canvas.draw()
    figure.set_layout_engine("none")
    background = figure.canvas.copy_from_bbox(figure.bbox)
    width, height = figure.canvas.get_width_height()

    path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        matplotlib.rcParams["animation.ffmpeg_path"], "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{width}x{height}", "-r", f"{frame_rate:g}", "-i", "-",
        "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", str(path),
    ]
    with subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE) as encoder:
        try:
            for frame in range(len(values)):
                figure.canvas.restore_region(background)
                draw(frame)
                for artist in moving:
                    artist.axes.draw_artist(artist)
                encoder.stdin.write(figure.canvas.buffer_rgba())
        finally:
            encoder.stdin.close()
            error = encoder.stderr.read().decode(errors="replace")
    plt.close(figure)
    if encoder.returncode:
        raise RuntimeError(f"ffmpeg failed: {error}")
    print(f"Saved {path} ({len(values)} frames, {len(values) / frame_rate:.1f} s at {frame_rate:g} fps)")
