"""Save a waterfall and PSD plot per test. Edit the settings, then run: pixi run view-events"""

from datetime import timedelta
from pathlib import Path

from beaverfiber import plot_events
from beaverfiber.plot_event import env_path

DATA_FOLDER = env_path("data_folder_nat")
EVENT_LIST = env_path("event_list_nat")
OUTPUT_DIR = Path(__file__).parent / "outputs" / DATA_FOLDER.name

TEST_IDS = [
    "TST-001", #vlak op kruin, zonder ruis
    "TST-002", #vlak op kruin, met ruis
    "TST-003", #talud net onder kruin, zonder ruis
    "TST-004", #talud net onder kruin, met ruis
    "TST-007-a", #talud net boven teen, zonder ruis
    "TST-007-b", #talud net boven teen, met ruis
    "TST-008", #vlak in veld, 4 meter van teen, zonder ruis
    "TST-009", #vlak in veld, 9 meter van teen, zonder ruis
    "TST-012", #vlak in het veld, 14 meter van teen, zonder ruis
    "TST-013", #zandtalud bij heg, zonder ruis

    "TST-001d", #vlak op kruin, zonder ruis
    "TST-002d", #vlak op kruin, met ruis
    "TST-003d", #talud net onder maar bijna op kruin, zonder ruis
    "TST-004d", #talud net onder maar bijna op kruin, met ruis
    "TST-007-d", #talud net boven teen (op 1/3 van de taludhoogte), zonder ruis
    "TST-009d", #vlak in veld, 8 meter van teen, zonder ruis
    "TST-013d", # teen van zandtalud bij heg, zonder ruis
]

MEASUREMENTS = [
    "1e stap, houten pootjes",
    "2e stap, houten pootjes intensief",
    "3e stap, hark",
    "4e stap, hark intensief",
    "5e stap, houten pootjes intensief / dieper dan zode",
    "6e stap, graven met de handen ( met handschoenen)"
]

# WARNING: local time in event list has changed DURING the survey (so +2 before 25 oktober, +1 after)
# TIME_DELTA = timedelta(hours=1, minutes=59, seconds=52.8)  # UTC = event-list time - TIME_DELTA.
TIME_DELTA = timedelta(hours=1, minutes=00, seconds=00)  # UTC = event-list time - TIME_DELTA.

NOISE_SECONDS = 10  # Seconds before the measurement.
SIGNAL_SECONDS = 10  # Seconds from the measurement onward.

FIBER_RANGE_M = (20, 1250)  # (start, end) in metres; None for the whole fiber.
NORMALIZE_CHANNELS = False  # Equalize channel amplitudes in the waterfall only.
BANDPASS_HZ = (10,30)  # e.g. (5, 200); None for no filter.
ENVELOPE = False  # Hilbert envelope after the bandpass, if any.
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
    envelope=ENVELOPE,
    interpolation=INTERPOLATION,
    clip_quantile=CLIP_QUANTILE,
    data_folder=DATA_FOLDER,
    event_list=EVENT_LIST,
    output_dir=OUTPUT_DIR,
    show=SHOW_PLOTS,
    write_segy=WRITE_SEGY,
)
