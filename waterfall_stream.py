"""Play the recordings as a scrolling waterfall movie. Edit the settings, then run: pixi run waterfall-stream"""

from pathlib import Path

from beaverfiber import stream_waterfall

START_DATETIME = "2026-10-12 11:01:00"
STOP_DATETIME = "2026-10-12 11:06:00"
TIMEZONE = "Europe/Amsterdam"  # Timezone of the two times above, e.g. "UTC" or "Etc/GMT-1" (= UTC+1).

FIBER_RANGE_M = (600, 1200)  # (start, end) in metres; None for the whole fiber.
NORMALIZE_CHANNELS = False  # Equalize channel amplitudes.
BANDPASS_HZ = None  # e.g. (5, 200); None for no filter.
INTERPOLATION = "kaiser"  # Waterfall smoothing, e.g. "nearest", "bilinear", "kaiser".
CLIP_QUANTILE = 0.99  # 1.0 shows the full amplitude range; lower values boost contrast.

DISPLAY_SECONDS = 10  # Seconds of data visible at once.
PLAYBACK_SPEED = 4.0  # Recorded seconds per real second.
FPS = 60  # Screen refreshes per second.
MAX_TIME_ROWS = 1000  # Time rows on screen; lower is faster.
PREFETCH_BLOCKS = 4  # Seconds of data read ahead.

ENV_FILE = Path(__file__).parent / ".env"

stream_waterfall(
    START_DATETIME,
    STOP_DATETIME,
    timezone_name=TIMEZONE,
    fiber_range_m=FIBER_RANGE_M,
    normalize_channels=NORMALIZE_CHANNELS,
    bandpass_hz=BANDPASS_HZ,
    interpolation=INTERPOLATION,
    clip_quantile=CLIP_QUANTILE,
    display_seconds=DISPLAY_SECONDS,
    playback_speed=PLAYBACK_SPEED,
    fps=FPS,
    max_time_rows=MAX_TIME_ROWS,
    prefetch_blocks=PREFETCH_BLOCKS,
    env_file=ENV_FILE,
)
