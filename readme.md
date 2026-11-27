# BeaverFiber

BeaverFiber visualizes Fiber-Optic DAS (Distributed Acoustic Sensing) recordings. Choose one of three tools:

| Tool | What it does |
|------|---|
| **view_events.py** | Save waterfall plots and noise/signal power spectra for specific tests |
| **waterfall_stream.py** | Play recordings as a scrolling waterfall animation |
| **event_movie.py** | Create map movies showing amplitude along the fiber over time (QGIS + MP4) |

## Quick Start

### 1. Install

[Install Pixi](https://pixi.sh), then in this folder run:

```powershell
pixi install
```

### 2. Configure your data

Copy the example settings file:

```powershell
Copy-Item .env_example .env
```

Edit `.env` and point to your HDF5 recordings folder:

```dotenv
data_folder = "C:/path/to/your/recordings"
```

The event lists (CSV files) are already in the `event_lists/` folder.

### 3. Run a tool

Edit one of these files, adjust the settings at the top, then run:

```powershell
pixi run view-events       # Plot waterfall + power spectrum
pixi run waterfall-stream  # Play as animated waterfall
pixi run event-movie       # Create QGIS layer + MP4 video
```

## Common Settings (all tools)

| Setting | Meaning |
|---------|---------|
| `TEST_IDS` | Which tests to process, e.g. `["TST-001", "TST-002"]` |
| `MEASUREMENTS` | Which measurement columns from the CSV to include |
| `TIME_DELTA` | Clock offset between event list and recordings (timedelta) |
| `FIBER_RANGE_M` | Fiber section to show, e.g. `(20, 1250)` or `None` for all |
| `BANDPASS_HZ` | Frequency filter range, e.g. `(5, 200)` or `None` for none |
| `CLIP_QUANTILE` | Color contrast: `0.99` clips strongest 1%, `1.0` shows full range |

## Tool-Specific Settings

### view_events.py

```python
NOISE_SECONDS = 10          # Pre-event window (seconds)
SIGNAL_SECONDS = 10         # Post-event window (seconds)
ENVELOPE = False            # Use Hilbert amplitude envelope
NORMALIZE_CHANNELS = False  # Equalize channel colors
INTERPOLATION = "kaiser"    # Waterfall smoothing
SHOW_PLOTS = False          # Open plots in a window
WRITE_SEGY = True           # Save as SEG-Y file
```

**Output:** `outputs/<folder>/<test>_<measurement>_waterfall_psd.png` and `.sgy`

### waterfall_stream.py

```python
START_DATETIME = "2026-10-12 11:01:00"
STOP_DATETIME = "2026-10-12 11:06:00"
TIMEZONE = "Europe/Amsterdam"
DISPLAY_SECONDS = 10        # Time window shown at once
PLAYBACK_SPEED = 4.0        # Speed factor (4x = 4 real seconds per 1 screen second)
MAX_TIME_ROWS = 1000        # Lower = faster but choppier
```

**Usage:** Press Space to pause/resume, close window to stop.

### event_movie.py

```python
SLICE_INTERVAL_S = 0.02     # Time between frames
UPSAMPLE_FACTOR = 4         # Map points per channel spacing
WRITE_GEOPACKAGE = True     # Create QGIS layer
WRITE_MP4 = True            # Create MP4 video
FRAME_RATE = 10             # MP4 fps
BASEMAP = "Esri.WorldImagery"  # Background ("None" for offline)
WATERFALL_INSET = True      # Show waterfall animation beside map
MAP_EXTENT_RD = None        # Zoom region or None for full fiber
```

**Output:** 
- `outputs/<folder>/<test>_<measurement>_time_slices.gpkg` (QGIS)
- `outputs/<folder>/<test>_<measurement>_time_slices.mp4` (video)

## Event List Format

Your CSV must include these columns (in any order):

```csv
Test-ID,Date,<measurement columns...>
IJK-001,12-10-2026,11:06:15,11:06:45
```

- **Test-ID**: Unique identifier matching your files
- **Date**: `DD-MM-YYYY` or `YYYY-MM-DD`
- **Measurement columns**: Any header names; times are `HH:MM:SS`

Supported encodings: UTF-8, UTF-8 with BOM, Windows-1252.

## Fiber Map (for event_movie.py)

The file `channel_fiber_map/channel_mapped_fiber.gpkg` maps HDF5 channels to their geographic positions. It's used automatically when creating MP4 movies and QGIS layers.

## Troubleshooting

| Error | Solution |
|-------|----------|
| **No valid time for...** | Check the measurement time is not empty in your CSV |
| **Recordings do not cover...** | Verify your time range exists in your HDF5 files |
| **Skipping unreadable...** | That HDF5 file may be damaged; check with another tool |

---

Your recordings are only read; they are never modified.
