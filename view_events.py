"""Save a waterfall and PSD plot per test. Edit the settings below, then run: pixi run view-events"""

from datetime import timedelta
from pathlib import Path

from beaverfiber import plot_events
from beaverfiber.plot_event import env_path

# ============================================================================
# EDIT THESE SETTINGS
# ============================================================================

DATA_FOLDER = env_path("data_folder")
EVENT_LIST = Path(__file__).resolve().parent / "event_lists" / "beaver_fiber_event_list_nat.csv"
OUTPUT_DIR = Path(__file__).parent / "outputs" / DATA_FOLDER.name

TEST_IDS = [
    "TST-001",
    "TST-002",
]

MEASUREMENTS = [
    "1e stap",
    "2e stap",
]

TIME_DELTA = timedelta(hours=1)  # UTC = event-list time - TIME_DELTA

NOISE_SECONDS = 10
SIGNAL_SECONDS = 10

FIBER_RANGE_M = (20, 1262)
NORMALIZE_CHANNELS = False
BANDPASS_HZ = (10, 30)
ENVELOPE = False
INTERPOLATION = "kaiser"
CLIP_QUANTILE = 0.8

SHOW_PLOTS = False
WRITE_SEGY = True


plot_events(
    TEST_IDS,
    measurements=MEASUREMENTS,
    time_delta=TIME_DELTA,
    noise_seconds=NOISE_SECONDS,
    signal_seconds=SIGNAL_SECONDS,
    fiber_range_m=FIBER_RANGE_M,
    normalize_channels=NORMALIZE_CHANNELS,
    bandpass_hz=BANDPASS_HZ,
    envelope=ENVELOPE,
    interpolation=INTERPOLATION,
    clip_quantile=CLIP_QUANTILE,
    data_folder=DATA_FOLDER,
    event_list=EVENT_LIST,
    output_dir=OUTPUT_DIR,
    show=SHOW_PLOTS,
    write_segy=WRITE_SEGY,
)
