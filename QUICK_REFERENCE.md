# Quick Reference Card

## Setup (One Time)

```powershell
# 1. Install Pixi from https://pixi.sh
# 2. In this folder:
pixi install

# 3. Copy settings template
Copy-Item .env_example .env

# 4. Edit .env with your data folder path
notepad .env
```

## Three Tools

| Tool | Command | Edit File | Output |
|------|---------|-----------|--------|
| Plot waterfall | `pixi run view-events` | `view_events.py` lines 11-26 | PNG + SEG-Y |
| Stream animation | `pixi run waterfall-stream` | `waterfall_stream.py` lines 5-15 | Live display |
| Map video + QGIS | `pixi run event-movie` | `event_movie.py` lines 11-33 | MP4 + GeoPackage |

## Most Common Settings to Edit

```python
# WHICH DATA TO PROCESS
TEST_IDS = ["TST-001", "TST-002"]  # Which tests to process
MEASUREMENTS = ["1e stap", "2e stap"]  # Which measurements from CSV

# HOW TO PROCESS
TIME_DELTA = timedelta(hours=1)  # Clock offset
BANDPASS_HZ = (5, 200)  # Frequency filter or None
CLIP_QUANTILE = 0.99  # Color boost (lower = more contrast)
FIBER_RANGE_M = (20, 1250)  # Zoom or None for all

# WHETHER TO SAVE
SHOW_PLOTS = False  # Show window? (True/False)
WRITE_SEGY = True  # Save SEG-Y format? (True/False)
WRITE_MP4 = True  # Save MP4 video? (True/False)
```

## Available Event Lists

```
event_lists/
├── beaver_fiber_event_list_nat.csv      # Natural (nat)
├── beaver_fiber_event_list_droog.csv    # Dry (droog)
├── beaver_fiber_event_list_ijken.csv    # Calibration (ijken)
└── beaver_fiber_event_list_vochtig.csv  # Wet (vochtig)
```

Pick one and use in your script:
```python
EVENT_LIST = Path(__file__).resolve().parent / "event_lists" / "beaver_fiber_event_list_nat.csv"
```

## CSV Format (Your Event Lists)

Your CSV should have these columns:

| Column | Format | Example |
|--------|--------|---------|
| `Test-ID` | Identifier | `TST-001` |
| `Date` | DD-MM-YYYY or YYYY-MM-DD | `12-10-2026` |
| **Measurement columns** | HH:MM:SS | `11:06:15` |

```csv
Test-ID,Date,1e stap,2e stap
TST-001,12-10-2026,11:06:15,11:06:45
TST-002,12-10-2026,11:08:20,11:08:50
```

## Troubleshooting

| Error | Try This |
|-------|----------|
| "No valid time for TEST-ID" | Check CSV—measurement time is empty |
| "Module h5py not found" | Run `pixi install` again |
| "Recordings do not cover..." | Your requested time range isn't in the HDF5 file |
| "No data displayed" | Try `CLIP_QUANTILE = 0.95` to boost contrast |
| "Movie is too large" | Use `SLICE_INTERVAL_S = 0.05` (fewer frames) or smaller `FIBER_RANGE_M` |

## File Locations

```
Outputs go here:          outputs/
Pre-made event lists:     event_lists/
Fiber coordinate map:     channel_fiber_map/channel_mapped_fiber.gpkg
Python library (read-only): src/beaverfiber/
```

## Documentation

- 📖 **STUDENT_START_HERE.md** – 5-minute guide
- 📖 **readme.md** – Full reference with all settings
- 📖 **CHANGES_SUMMARY.md** – What was cleaned up
- 📖 **This file** – Quick reference card

---

**Need Help?** Read the first few sections of `readme.md` or `STUDENT_START_HERE.md` 🚀
