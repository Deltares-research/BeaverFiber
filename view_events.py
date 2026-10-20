"""Save a waterfall and PSD plot per test. Edit the settings, then run: pixi run view-events"""

from datetime import timedelta
from pathlib import Path

from beaverfiber import plot_events

TEST_IDS = ["IJK-001", "IJK-027"]  # Test-IDs from the event list.
MEASUREMENT = "1e meting"  # "1e meting" or "2e meting".
TIME_DELTA = timedelta(hours=1, minutes=59, seconds=52.8)  # UTC = event-list time - TIME_DELTA.

NOISE_SECONDS = 2  # Seconds before the measurement.
SIGNAL_SECONDS = 2  # Seconds from the measurement onward.

FIBER_RANGE_M = (20, 1250)  # (start, end) in metres; None for the whole fiber.
NORMALIZE_CHANNELS = False  # Equalize channel amplitudes in the waterfall only.
BANDPASS_HZ = None  # e.g. (5, 200); None for no filter.
INTERPOLATION = "kaiser"  # Waterfall smoothing, e.g. "nearest", "bilinear", "kaiser".
CLIP_QUANTILE = 0.8  # 1.0 shows the full amplitude range; lower values boost contrast.

SHOW_PLOTS = False  # True opens each plot in a window.
WRITE_SEGY = True  # Also save the plotted data as a .sgy file.
OUTPUT_DIR = Path(__file__).parent / "outputs"
ENV_FILE = Path(__file__).parent / ".env"

plot_events(
    TEST_IDS,
    measurement=MEASUREMENT,
    time_delta=TIME_DELTA,
    noise_seconds=NOISE_SECONDS,
    signal_seconds=SIGNAL_SECONDS,
    fiber_range_m=FIBER_RANGE_M,
    normalize_channels=NORMALIZE_CHANNELS,
    bandpass_hz=BANDPASS_HZ,
    interpolation=INTERPOLATION,
    clip_quantile=CLIP_QUANTILE,
    env_file=ENV_FILE,
    output_dir=OUTPUT_DIR,
    show=SHOW_PLOTS,
    write_segy=WRITE_SEGY,
)
