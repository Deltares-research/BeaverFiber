"""Map movie of DAS amplitudes along the fiber (QGIS GeoPackage + MP4). Edit the settings below, then run: pixi run event-movie"""

from datetime import timedelta
from pathlib import Path

from beaverfiber import make_event_movies
from beaverfiber.plot_event import env_path

ROOT = Path(__file__).resolve().parent
DATA_FOLDER = env_path("data_folder")
EVENT_LIST = ROOT / "event_lists" / "beaver_fiber_event_list_nat.csv"
FIBER_MAP = ROOT / "channel_fiber_map" / "channel_mapped_fiber.gpkg"
OUTPUT_DIR = ROOT / "outputs" / DATA_FOLDER.name

# ============================================================================
# EDIT THESE SETTINGS
# ============================================================================

TEST_IDS = [
    "TST-001",
]

MEASUREMENTS = [
    "1e stap",
]

TIME_DELTA = timedelta(hours=1)

NOISE_SECONDS = 5
SIGNAL_SECONDS = 10

FIBER_RANGE_M = (20, 1262)
BANDPASS_HZ = (10, 30)
ENVELOPE = True
NORMALIZE_CHANNELS = False
CLIP_QUANTILE = 0.99

SLICE_INTERVAL_S = 0.02
UPSAMPLE_FACTOR = 4

WRITE_GEOPACKAGE = True
WRITE_MP4 = True
FRAME_RATE = 10
BASEMAP = "Esri.WorldImagery"
WATERFALL_INSET = True
MAP_EXTENT_RD = None
LINE_WIDTH = 4


make_event_movies(
    TEST_IDS,
    measurements=MEASUREMENTS,
    time_delta=TIME_DELTA,
    noise_seconds=NOISE_SECONDS,
    signal_seconds=SIGNAL_SECONDS,
    fiber_range_m=FIBER_RANGE_M,
    normalize_channels=NORMALIZE_CHANNELS,
    bandpass_hz=BANDPASS_HZ,
    envelope=ENVELOPE,
    clip_quantile=CLIP_QUANTILE,
    slice_interval_s=SLICE_INTERVAL_S,
    upsample_factor=UPSAMPLE_FACTOR,
    data_folder=DATA_FOLDER,
    event_list=EVENT_LIST,
    fiber_map=FIBER_MAP,
    output_dir=OUTPUT_DIR,
    write_geopackage=WRITE_GEOPACKAGE,
    write_mp4=WRITE_MP4,
    frame_rate=FRAME_RATE,
    basemap=BASEMAP,
    waterfall_inset=WATERFALL_INSET,
    map_extent_rd=MAP_EXTENT_RD,
    line_width=LINE_WIDTH,
)
