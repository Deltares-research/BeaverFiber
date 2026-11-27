# 🎓 Student Quick Start Guide

Welcome! BeaverFiber is now simplified for you. This guide gets you up and running in 5 minutes.

## What is BeaverFiber?

BeaverFiber visualizes Fiber-Optic DAS (Distributed Acoustic Sensing) recordings—think of it as a tool to look at vibrations recorded along a fiber-optic cable.

You have **three tools** to choose from:

1. **Plot waterfall diagrams** - See all the vibration data at once with colors
2. **Stream waterfall animation** - Watch the data play back in real-time
3. **Create map videos** - Show vibration activity on a geographic map as a video

## Installation (1 minute)

1. **Install [Pixi](https://pixi.sh)** (a package manager for Python)

2. **Open PowerShell in this folder** and run:
   ```powershell
   pixi install
   ```

Done! ✅

## Setup your data (2 minutes)

1. **Copy the settings file:**
   ```powershell
   Copy-Item .env_example .env
   ```

2. **Edit `.env`** and point to your HDF5 recordings folder. For example:
   ```dotenv
   data_folder = "C:/Users/YourName/Desktop/my_recordings"
   ```

## Run a tool (2 minutes)

Pick **one** tool below and edit it:

### Tool 1: Plot Waterfall + Power Spectrum
```powershell
# Edit view_events.py at the top (line 11-26):
# - Set which test IDs to plot
# - Set which measurements to include
# 
# Then run:
pixi run view-events

# Output: PNG plots in outputs/
```

### Tool 2: Stream Waterfall Animation
```powershell
# Edit waterfall_stream.py at the top (line 5-15):
# - Set START_DATETIME and STOP_DATETIME
# - Adjust speed, zoom, etc.
#
# Then run:
pixi run waterfall-stream

# Press Space to pause/resume, close window to stop
```

### Tool 3: Create Map Video + QGIS Layer
```powershell
# Edit event_movie.py at the top (line 11-33):
# - Set which test IDs and measurements
# - Adjust video settings (frame rate, zoom, etc.)
#
# Then run:
pixi run event-movie

# Output: MP4 video + GeoPackage file in outputs/
# Open GeoPackage in QGIS for interactive temporal playback
```

## CSV Event Lists

Your event lists are pre-made and in the `event_lists/` folder:
- `beaver_fiber_event_list_nat.csv`
- `beaver_fiber_event_list_droog.csv`
- `beaver_fiber_event_list_ijken.csv`
- `beaver_fiber_event_list_vochtig.csv`

Just set them in your Python scripts and go!

## Common Settings (All Tools)

| Setting | Meaning | Example |
|---------|---------|---------|
| `TEST_IDS` | Which tests to plot | `["TST-001", "TST-002"]` |
| `MEASUREMENTS` | Which columns from CSV | `["1e stap", "2e stap"]` |
| `FIBER_RANGE_M` | Zoom into a cable section | `(20, 1250)` or `None` for all |
| `BANDPASS_HZ` | Filter frequencies | `(5, 200)` or `None` to skip |
| `CLIP_QUANTILE` | Color brightness: `0.99` = boost weak signals, `1.0` = full range | `0.99` |

## Need More Help?

📖 Read the full **[readme.md](readme.md)** for all settings and details.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "No valid time for..." | Check your CSV—measurement time might be empty |
| "Recordings do not cover..." | Your time range is not in the HDF5 file. Check dates/times |
| "Module not found" | Run `pixi install` again |
| Video or plot looks wrong | Adjust `CLIP_QUANTILE` or `BANDPASS_HZ` |

---

**Remember:** Your recordings are only read—never modified. Feel free to experiment! 🚀
