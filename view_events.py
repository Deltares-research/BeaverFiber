"""Edit the inputs below, then run: pixi run python view_events.py."""

from pathlib import Path

from beaverfiber import plot_events

TIME_WINDOW_UTC = None
EVENT_TIMEZONE = "Europe/Amsterdam"

TEST_IDS = [
    "IJK-002",
    "PRF-001g1",
    "PRF-001g2",
    "PRF-001h1",
    "PRF-001h2",
    "PRF-002g1",
    "PRF-002g2",
    "PRF-002h1",
    "PRF-002h2",
    "PRF-003g1",
    "PRF-003g2",
    "PRF-003h1",
    "PRF-003h2",
]

BEFORE_SECONDS = 2
AFTER_SECONDS = 2

CHANNELS = None
CHANNEL_RANGE = None
NORMALIZE_CHANNELS = True
BANDPASS_HZ = None

ENV_FILE = Path(__file__).resolve().parent / ".env"
OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"
SHOW_PLOTS = False


if __name__ == "__main__":
    plot_events(
        test_ids=TEST_IDS,
        time_window_utc=TIME_WINDOW_UTC,
        event_timezone=EVENT_TIMEZONE,
        before_seconds=BEFORE_SECONDS,
        after_seconds=AFTER_SECONDS,
        channels=CHANNELS,
        channel_range=CHANNEL_RANGE,
        normalize_channels=NORMALIZE_CHANNELS,
        bandpass_hz=BANDPASS_HZ,
        env_file=ENV_FILE,
        output_dir=OUTPUT_DIR,
        show=SHOW_PLOTS,
    )