# BeaverFiber

BeaverFiber selects time windows from OptoDAS distributed acoustic sensing (DAS)
HDF5 recordings and saves a waterfall image and a power spectral density (PSD)
plot. Select tests from an event-list CSV or supply a manual UTC time window.

Original recordings are opened read-only and are never changed.

## 1. Install

The included Pixi environment supports Windows. Install [Pixi](https://pixi.sh),
clone this repository, and open a PowerShell terminal in the project folder:

```powershell
pixi install
```

Pixi installs Python, the required libraries, and the BeaverFiber package. You do
not need to activate an environment before using the commands below.

## 2. Configure your data

For a new checkout, create your local configuration:

```powershell
Copy-Item .env_example .env
```

Edit `.env` to point to your recordings and event list. Forward slashes work in
Windows paths:

```dotenv
data_folder = "C:/DAS/recordings"
event_list = "C:/DAS/events.csv"
```

The recording folder is searched recursively. Relative paths are resolved from
the directory containing `.env`. Your `.env`, recordings, and generated outputs
are excluded from Git.

### Event-list CSV

Use a UTF-8, comma-separated CSV with these column names. Additional columns,
such as coordinates and notes, are allowed.

```csv
Test-ID,Date,1e meting,2e meting
IJK-002,12-10-2026,11:06:15,11:06:45
```

- `Test-ID`: the test identifier, for example `IJK-002` or `PRF-001g1`.
- `Date`: `DD-MM-YYYY` or `YYYY-MM-DD`.
- `1e meting` and `2e meting`: actual measurement times in `HH:MM:SS` format.
  Leave an unknown time blank, not `nan`. At least one actual time is required.

These are measurement instants, not planned times. The selected window spans the
earliest through latest measurement, plus the requested context.

**Timezones matter:** the event list is interpreted using `EVENT_TIMEZONE` in the
user script. `Europe/Amsterdam` handles Dutch winter and summer time. For example,
11:06:15 CEST on 12 October 2026 becomes 09:06:15 UTC. HDF5 timestamps and plot
axes use UTC.

## 3. Select and plot

Open `view_events.py` and edit the input settings at the top. It imports the
package; file selection, loading, and plotting happen inside BeaverFiber.

For example, select one test:

```python
TIME_WINDOW_UTC = None
EVENT_TIMEZONE = "Europe/Amsterdam"
TEST_IDS = ["IJK-002"]

BEFORE_SECONDS = 10
AFTER_SECONDS = 10
CHANNELS = None
CHANNEL_RANGE = None
NORMALIZE_CHANNELS = True
BANDPASS_HZ = None
SHOW_PLOTS = False
```

Run:

```powershell
pixi run view-events
```

Each selected ID produces `outputs/<Test-ID>_waterfall_psd.png`. Repeating a run
for the same ID overwrites that PNG. `OUTPUT_DIR` changes the destination.
`SHOW_PLOTS = False` saves without opening windows; `True` also opens each plot.
The terminal reports the selected UTC window and source recordings.

### Manual time window

Set `TIME_WINDOW_UTC` to an exact start/end pair:

```python
TIME_WINDOW_UTC = (
    "2026-10-12 09:06:05",
    "2026-10-12 09:06:55",
)
```

This overrides `TEST_IDS`, `EVENT_TIMEZONE`, and the before/after durations. No
event list is needed in manual mode. Start is included and end is excluded,
subject to the recording's sample grid. Timestamps without an offset mean UTC;
ISO timestamps with `Z` or an explicit offset are also accepted.

Set it back to `None` to use the event list. Manual PNG names contain their UTC
start and end timestamps and have no measurement markers.

### Channel selection

Leave both selectors as `None` for the full recorded fiber. Otherwise, set only
one:

```python
CHANNELS = [0, 98, 200]
CHANNEL_RANGE = None
```

Or use an inclusive channel-ID interval:

```python
CHANNELS = None
CHANNEL_RANGE = (4, 176)
```

These are IDs from the HDF5 header, not array-column numbers or distances in
metres. The plot uses the corresponding fiber-distance metadata. No geographic
coordinate-to-fiber mapping is performed.

### Normalization and filtering

`NORMALIZE_CHANNELS = True` makes weak spatial patterns easier to see when some
channels are much noisier than others. For display only, each channel is divided
by its 75th-percentile absolute amplitude in the selected window, with a minimum
scale of one count. Colors use fixed limits of +/-3. This does not affect the
PSD, but normalized colors cannot be compared as absolute amplitudes between
channels or events. Set it to `False` for raw-count colors.

`BANDPASS_HZ = None` disables additional filtering. A pair enables it:

```python
BANDPASS_HZ = (2.0, 40.0)
```

The Butterworth bandpass is applied per channel to the joined time window, using
second-order sections and forward/backward zero-phase filtering. It affects both
the waterfall and PSD, before display normalization. The passband is shown in
the figure. Cutoffs must satisfy `0 < LOW < HIGH < sample_rate / 2`.

The example frequencies are a starting point, not an optimum for every signal.
Include enough time before and after an event: edge effects and pre-ringing can
affect apparent onset times, even with zero-phase filtering. Compare timing
against unfiltered data.

## 4. Read the plots

- **Waterfall:** horizontal axis is fiber distance; vertical axis is UTC time,
  increasing downward. Red and blue represent opposite signal signs. Dashed
  lines mark actual measurement times in ID mode.
- **Raw colors:** limits are symmetric and use the 99th percentile of absolute
  counts. Values outside the limits saturate the colors; they are not deleted.
- **PSD:** the mean of individual selected-channel Welch spectra over the entire
  window. Units are counts squared per Hz. It uses Hann segments up to two
  seconds long with 50% overlap; the DC bin is not plotted.

Plots use stored integer counts, or filtered counts when enabled, not calibrated
strain. Display normalization never changes the PSD. All selected channels,
including zero-only channels, contribute to the PSD average.

Fiber distances are measurement locations, not geographic coordinates. Gauge
length is different from channel spacing; both depend on acquisition metadata.

## Troubleshooting

- **No recordings overlap:** check the event date, timezone, and archive coverage.
  Do not shift times simply to select a stronger-looking signal.
- **Unreadable file warning:** the file is skipped and its path/error is printed.
  Recopy or inspect it. If this leaves a gap in the requested window, plotting
  fails rather than concealing the missing data.
- **Gap, overlap, or changed settings:** the requested data must be continuous and
  have compatible sampling and channel/distance metadata.
- **Invalid event time:** replace `nan` with a real measurement time or leave it
  blank if another actual time is available. Planned times are not a fallback.
- **Filtering error:** check the cutoffs and use a longer time window.
- **Blank part of the fiber:** the stored samples may be zero there. Increasing
  display gain cannot create missing signal.

## Other interfaces

The package can be imported from another Python script:

```python
from beaverfiber import plot_events

paths = plot_events(
    test_ids=["IJK-002"],
    env_file=".env",
    event_timezone="Europe/Amsterdam",
    normalize_channels=True,
    show=False,
)
```

It returns the saved figure paths. It is also installable with `pip install .`
in an existing Python environment.

The command-line interface offers the same options:

```powershell
pixi run beaverfiber-plot --test-ids IJK-002 --normalize-channels --no-show
pixi run beaverfiber-plot --help
```

Run the focused tests:

```powershell
pixi run test
```