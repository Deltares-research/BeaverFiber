"""Play recordings as a scrolling waterfall movie, reading ahead in a background thread."""

import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event as Flag, Thread
from zoneinfo import ZoneInfo

import numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi

from .plot_event import color_limit, env_path, extract_window, scan_recordings, waterfall_image


@dataclass
class Block:
    values: np.ndarray  # Display rows x channels.
    ends: np.ndarray  # UTC timestamp at the end of each row.
    distances: np.ndarray


def to_utc(value: str | datetime, timezone_name: str) -> datetime:
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(timezone_name))
    return parsed.astimezone(timezone.utc)


def peak_rows(values: np.ndarray, stride: int) -> np.ndarray:
    """Reduce every `stride` samples to the signed sample with the largest magnitude."""
    rows = []
    for first in range(0, len(values), stride):
        part = values[first:first + stride]
        rows.append(np.take_along_axis(part, np.abs(part).argmax(axis=0)[None, :], axis=0)[0])
    return np.array(rows, dtype=np.float32)


def read_blocks(recordings, start: float, stop: float, dt: float, stride: int, fiber_range_m,
                normalize_channels: bool, bandpass_hz):
    """Yield about one second of display rows at a time."""
    chunk = max(1, math.ceil(1 / dt / stride)) * stride * dt
    sections = state = scales = None
    if bandpass_hz is not None:
        if not 0 < bandpass_hz[0] < bandpass_hz[1] < 0.5 / dt:
            raise ValueError(f"BANDPASS_HZ must satisfy 0 < LOW < HIGH < {0.5 / dt:g} Hz")
        sections = butter(4, bandpass_hz, btype="bandpass", fs=1 / dt, output="sos")
    for index in range(math.ceil((stop - start) / chunk)):
        left = start + index * chunk
        window = extract_window(recordings, left, min(left + chunk, stop), fiber_range_m)
        values = window.counts.astype(np.float64)
        if sections is not None:
            # Causal filter; the state carries over so block edges are seamless.
            if state is None:
                state = sosfilt_zi(sections)[:, :, None] * values[0]
            values, state = sosfilt(sections, values, axis=0, zi=state)
        if normalize_channels:
            # Scale with the first block so amplitudes stay comparable over time.
            if scales is None:
                scales = np.maximum(np.percentile(np.abs(values), 75, axis=0), 1)
            values = values / scales
        row_ends = np.minimum(np.arange(stride, len(values) + stride, stride), len(values))
        yield Block(peak_rows(values, stride), window.timestamps[row_ends - 1] + dt, window.distances)


class Prefetch:
    """Reads blocks in a background thread so the movie never waits for the disk."""

    def __init__(self, blocks, capacity: int):
        self.queue = Queue(maxsize=capacity)
        self.stopped = Flag()
        self.thread = Thread(target=self._run, args=(blocks,), daemon=True)
        self.thread.start()

    def _put(self, item) -> bool:
        while not self.stopped.is_set():
            try:
                self.queue.put(item, timeout=0.05)
                return True
            except Full:
                pass
        return False

    def _run(self, blocks) -> None:
        try:
            for block in blocks:
                if not self._put(block):
                    return
        except Exception as error:
            self._put(error)
        self._put(None)

    def get(self, wait: bool = False):
        item = self.queue.get() if wait else self.queue.get_nowait()
        if isinstance(item, Exception):
            raise item
        return item

    def stop(self) -> None:
        self.stopped.set()
        self.thread.join()


class Playback:
    """Moves the playhead at the requested speed and keeps the visible rows."""

    def __init__(self, reader: Prefetch, first: Block, rows: int, row_seconds: float, speed: float):
        self.reader, self.block, self.offset = reader, first, 0
        self.values = np.full((rows, first.values.shape[1]), np.nan, dtype=np.float32)
        self.row_seconds, self.speed = row_seconds, speed
        self.playhead = first.ends[0]
        self.paused = self.finished = self.buffering = False
        self.credit = 0.0
        self.last_tick = time.perf_counter()

    def advance(self) -> None:
        now = time.perf_counter()
        elapsed, self.last_tick = now - self.last_tick, now
        if self.paused or self.finished:
            return
        self.credit = min(len(self.values), self.credit + elapsed * self.speed / self.row_seconds)
        self.buffering = False
        while self.credit >= 1:
            if self.offset == len(self.block.values):
                try:
                    following = self.reader.get()
                except Empty:
                    self.buffering, self.credit = True, 0
                    return
                if following is None:
                    self.finished = True
                    return
                self.block, self.offset = following, 0
            count = min(int(self.credit), len(self.block.values) - self.offset)
            self.values[:-count] = self.values[count:]
            self.values[-count:] = self.block.values[self.offset:self.offset + count]
            self.offset += count
            self.playhead = self.block.ends[self.offset - 1]
            self.credit -= count


def stream_waterfall(
    start_datetime: str | datetime, stop_datetime: str | datetime, *, timezone_name: str,
    fiber_range_m: tuple[float, float] | None, normalize_channels: bool,
    bandpass_hz: tuple[float, float] | None, interpolation: str, clip_quantile: float,
    display_seconds: float, playback_speed: float, fps: float, max_time_rows: int,
    prefetch_blocks: int, env_file: str | Path,
) -> None:
    """Play the waterfall; Space or the button pauses, closing the window stops."""
    import matplotlib.pyplot as plt
    from matplotlib.widgets import Button

    start = to_utc(start_datetime, timezone_name)
    stop = to_utc(stop_datetime, timezone_name)
    if stop <= start:
        raise ValueError("STOP_DATETIME must be later than START_DATETIME")
    recordings = scan_recordings(env_path(env_file, "data_folder"))
    dt = recordings[0].dt
    stride = max(1, math.ceil(display_seconds / dt / max_time_rows))
    row_seconds = stride * dt
    blocks = read_blocks(recordings, start.timestamp(), stop.timestamp(), dt, stride,
                         fiber_range_m, normalize_channels, bandpass_hz)
    reader = Prefetch(blocks, prefetch_blocks)
    try:
        first = reader.get(wait=True)
        if first is None:
            raise ValueError("No samples in the requested time")
        distances = first.distances
        rows = math.ceil(display_seconds / row_seconds)
        playback = Playback(reader, first, rows, row_seconds, playback_speed)
        print(f"Stream {start:%Y-%m-%d %H:%M:%S} to {stop:%H:%M:%S} UTC at {playback_speed:g}x, "
              f"fiber {distances[0]:.1f}-{distances[-1]:.1f} m ({len(distances)} channels)")

        figure, axes = plt.subplots(figsize=(11, 7), dpi=80)
        limit = color_limit(first.values, clip_quantile)
        image = waterfall_image(axes, distances, playback.values, (-rows * row_seconds, 0),
                                interpolation, cmap="RdBu_r", vmin=-limit, vmax=limit, animated=True)
        axes.invert_yaxis()
        filtered = "" if bandpass_hz is None else f" | causal bandpass {bandpass_hz[0]:g}-{bandpass_hz[1]:g} Hz"
        axes.set(xlabel="Fiber distance (m)", ylabel="Seconds before playhead",
                 title=f"Fiber {distances[0]:.1f}-{distances[-1]:.1f} m{filtered}")
        label = "Normalized counts" if normalize_channels else "Counts"
        figure.colorbar(image, ax=axes, label=f"{label} (clip quantile {clip_quantile:g})", extend="both")
        figure.subplots_adjust(bottom=0.17, top=0.86)
        status = axes.text(0, 1.015, "", transform=axes.transAxes, animated=True)
        button = Button(figure.add_axes((0.43, 0.04, 0.14, 0.05)), "Pause")
        timer = figure.canvas.new_timer(interval=round(1000 / fps))
        background = None

        def on_draw(_event) -> None:
            nonlocal background
            background = figure.canvas.copy_from_bbox(figure.bbox)
            draw_frame()

        def draw_frame() -> None:
            if background is None:
                return
            figure.canvas.restore_region(background)
            axes.draw_artist(image)
            axes.draw_artist(status)
            figure.canvas.blit(figure.bbox)

        def toggle(_event) -> None:
            playback.paused = not playback.paused
            playback.credit, playback.last_tick = 0, time.perf_counter()
            button.label.set_text("Resume" if playback.paused else "Pause")
            figure.canvas.draw_idle()

        def update() -> None:
            began = time.perf_counter()
            playback.advance()
            # Colouring before resampling is much faster than letting imshow do it.
            image.set_array(image.to_rgba(np.ma.masked_invalid(playback.values), bytes=True))
            state = ("Finished" if playback.finished else "Paused" if playback.paused
                     else "Buffering" if playback.buffering else "Playing")
            clock = datetime.fromtimestamp(playback.playhead, timezone.utc)
            status.set_text(f"{clock:%Y-%m-%d %H:%M:%S.%f} UTC | {playback_speed:g}x | {state}")
            draw_frame()
            if playback.finished:
                timer.stop()
            timer.interval = max(1, round(1000 / fps - (time.perf_counter() - began) * 1000))

        button.on_clicked(toggle)
        figure.canvas.mpl_connect("key_press_event", lambda event: toggle(event) if event.key == " " else None)
        figure.canvas.mpl_connect("close_event", lambda _event: timer.stop())
        figure.canvas.mpl_connect("draw_event", on_draw)
        timer.add_callback(update)
        timer.start()
        plt.show()
    finally:
        reader.stop()
