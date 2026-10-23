"""Save a waterfall and PSD plot per test. Edit the settings, then run: pixi run view-events"""

from datetime import timedelta
from pathlib import Path

from beaverfiber import plot_events
from beaverfiber.plot_event import env_path

DATA_FOLDER = env_path("data_folder_droog")
EVENT_LIST = env_path("event_list_dry")
OUTPUT_DIR = Path(__file__).parent / "outputs"

TEST_IDS = [
    "TST-001d",
    "TST-002d",
    "TST-003d",
    "TST-004d",
]  

MEASUREMENTS = [
    "1e stap, houten pootjes",
    "2e stap, houten pootjes intensief",
    "3e stap, hark",
    "4e stap, hark intensief",
    "5e stap, houten pootjes intensief / dieper dan zode",
]

# TIME_DELTA = timedelta(hours=1, minutes=59, seconds=52.8)  # UTC = event-list time - TIME_DELTA.
TIME_DELTA = timedelta(hours=2, minutes=00, seconds=00)  # UTC = event-list time - TIME_DELTA.

NOISE_SECONDS = 10  # Seconds before the measurement.
SIGNAL_SECONDS = 10  # Seconds from the measurement onward.

FIBER_RANGE_M = (20, 1250)  # (start, end) in metres; None for the whole fiber.
NORMALIZE_CHANNELS = False  # Equalize channel amplitudes in the waterfall only.
BANDPASS_HZ = None  # e.g. (5, 200); None for no filter.
INTERPOLATION = "kaiser"  # Waterfall smoothing, e.g. "nearest", "bilinear", "kaiser".
CLIP_QUANTILE = 0.8  # 1.0 shows the full amplitude range; lower values boost contrast.

SHOW_PLOTS = False  # True opens each plot in a window.
WRITE_SEGY = True  # Also save the plotted data as a .sgy file.


plot_events(
    TEST_IDS,
    measurements=MEASUREMENTS,
    time_delta=TIME_DELTA,
    noise_seconds=NOISE_SECONDS,
    signal_seconds=SIGNAL_SECONDS,
    fiber_range_m=FIBER_RANGE_M,
    normalize_channels=NORMALIZE_CHANNELS,
    bandpass_hz=BANDPASS_HZ,
    interpolation=INTERPOLATION,
    clip_quantile=CLIP_QUANTILE,
    data_folder=DATA_FOLDER,
    event_list=EVENT_LIST,
    output_dir=OUTPUT_DIR,
    show=SHOW_PLOTS,
    write_segy=WRITE_SEGY,
)
