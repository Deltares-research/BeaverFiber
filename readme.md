# BeaverFiber

BeaverFiber plots OptoDAS fiber-optic (DAS) recordings stored as `.hdf5` files:

- **`view_events.py`** saves a waterfall plot and a noise/signal power spectrum
  (PSD) for each test in your event list, and optionally a SEG-Y file.
- **`waterfall_stream.py`** plays the recordings as a scrolling waterfall movie.

Your recordings are only read, never changed.

## 1. Install

Install [Pixi](https://pixi.sh), then open PowerShell in this folder and run:

```powershell
pixi install
```

## 2. Point to your data

Copy the example settings file:

```powershell
Copy-Item .env_example .env
```

Open `.env` and set the folder with your `.hdf5` recordings (subfolders are
included) and the path to your event list:

```dotenv
data_folder = "C:/DAS/recordings"
data_folder_ijken = "C:/DAS/recordings/ijken"
data_folder_droog = "C:/DAS/recordings/droog"
event_list = "C:/DAS/events.csv"
event_list_dry = "C:/DAS/events_dry.csv"
```

`view_events.py` reads `data_folder_ijken` and `event_list` from `.env` and
passes those paths to `plot_events`. To use the dry measurements, change the
keys in its `DATA_FOLDER` and `EVENT_LIST` settings to `data_folder_droog` and
`event_list_dry`. The shared `env_path("key")` helper always reads `.env` from
the project root, independently of the current working directory. Relative
paths are resolved relative to `.env`; missing or empty values raise an error.
`waterfall_stream.py` uses `data_folder`.

The event list is a CSV file with `Test-ID`, `Date`, and measurement
time columns selected by their exact headers, regardless of column position. For example:

```csv
Test-ID,Geplande Tijd (NTP),1e meting,2e meting,Date
IJK-002,10:32:00,11:06:15,11:06:45,12-10-2026
```

- `Date`: required for each selected test, as `DD-MM-YYYY` or `YYYY-MM-DD`.
- Measurement headers may have any name. Only the headers listed in
  `MEASUREMENTS` are used; no columns are automatically selected.
  Times must be `HH:MM:SS`; a missing/invalid time raises an error.
- UTF-8 (with or without BOM) and Windows cp1252 CSV files are supported
  automatically. The reader reports when it uses cp1252.

## 3. Plot events

Open `view_events.py`, edit the settings at the top, and run:

```powershell
pixi run view-events
```

| Setting | Meaning |
|---|---|
| `TEST_IDS` | Tests to plot, e.g. `["IJK-001", "IJK-027"]`. |
| `MEASUREMENTS` | Non-empty list of exact CSV headers, e.g. `["1e meting", "2e meting"]`. |
| `TIME_DELTA` | Clock difference between the event list and the recordings (UTC): UTC = event-list time − `TIME_DELTA`. |
| `NOISE_SECONDS` | Seconds before the measurement (the noise window). |
| `SIGNAL_SECONDS` | Seconds from the measurement onward (the signal window). |
| `FIBER_RANGE_M` | Part of the fiber to show, in metres, e.g. `(20, 1250)`. `None` shows the whole fiber. |
| `NORMALIZE_CHANNELS` | `True` gives every channel a similar color strength in the waterfall. |
| `BANDPASS_HZ` | Frequency filter, e.g. `(5, 200)`. `None` means no filter. |
| `INTERPOLATION` | Waterfall smoothing: `"nearest"` (none), `"bilinear"`, `"kaiser"`, ... |
| `CLIP_QUANTILE` | Color contrast. `1.0` shows the full amplitude range; `0.99` clips the strongest 1 %, making weak signals easier to see. |
| `SHOW_PLOTS` | `True` opens every plot in a window. |
| `WRITE_SEGY` | `True` also saves a `.sgy` file to open in seismic software. |

Results are saved in `outputs/`, for example
`IJK-001_1e_meting_waterfall_psd.png` (and `.sgy`).

The waterfall shows fiber distance horizontally and time (UTC) vertically, with
a dashed line at the measurement. The PSD panel compares the average spectrum of
the noise window with that of the signal window.

The SEG-Y file contains the same samples as the plot (with the bandpass filter,
if set), one trace per channel. The fiber distance is stored as receiver X
(in millimetres, scalar −1000) and the exact start and measurement times are in
the text header.

## 4. Play a waterfall movie

Open `waterfall_stream.py`, set `START_DATETIME`, `STOP_DATETIME` and the other
settings, and run:

```powershell
pixi run waterfall-stream
```

Press **Space** or click **Pause** to pause; close the window to stop.

`TIMEZONE` is the time zone of the start and stop times, for example
`"Europe/Amsterdam"` or `"UTC"`. For a fixed offset use `"Etc/GMT-1"` for
UTC+1 or `"Etc/GMT+1"` for UTC−1 (the sign is reversed).

If the movie stutters, lower `MAX_TIME_ROWS`, `FPS` or `PLAYBACK_SPEED`, or
select a shorter `FIBER_RANGE_M`.

## Common errors

- **No valid ... time for ...**: the measurement time for that test is empty in
  the event list.
- **Recordings do not cover the complete requested time** or **Gap in
  recordings**: part of the requested time is missing from your recordings.
- **Skipping unreadable recording ...**: that `.hdf5` file is damaged or
  incomplete; it is ignored.
