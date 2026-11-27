# 🚀 BeaverFiber - Start Here!

Welcome! This is a tool to visualize **Fiber-Optic DAS (Distributed Acoustic Sensing) recordings**—like watching vibrations along a cable.

## 📚 Which Document Should I Read?

**Pick ONE below based on your situation:**

| Situation | Read This | Time |
|-----------|-----------|------|
| **I'm new and want to get started fast** | [STUDENT_START_HERE.md](STUDENT_START_HERE.md) | 5 min |
| **I need to quickly look something up** | [QUICK_REFERENCE.md](QUICK_REFERENCE.md) | 2 min |
| **I want the full technical reference** | [readme.md](readme.md) | 15 min |
| **I want to know what changed** | [CHANGES_SUMMARY.md](CHANGES_SUMMARY.md) | 5 min |

## 🎯 Quick Answer: How Do I Use BeaverFiber?

**In 3 steps:**

```powershell
# 1. Install (one time)
pixi install

# 2. Configure (one time)
Copy-Item .env_example .env
# Edit .env with your recordings folder

# 3. Run (every time you want results)
pixi run view-events           # Plot waterfall
pixi run waterfall-stream      # Animate waterfall  
pixi run event-movie           # Create map video
```

## 🛠️ The Three Tools

| Tool | Purpose | Edit File | Output |
|------|---------|-----------|--------|
| **view_events.py** | Static plot: waterfall + power spectrum | Lines 11-26 | PNG + SEG-Y |
| **waterfall_stream.py** | Live animation: watch data play | Lines 5-15 | On-screen |
| **event_movie.py** | Map video + interactive QGIS layer | Lines 11-33 | MP4 + GeoPackage |

## 📂 What's in This Repository?

```
BeaverFiber/
├── 📖 STUDENT_START_HERE.md    ← 5-min intro for students
├── 📖 QUICK_REFERENCE.md       ← Lookup tables & FAQ
├── 📖 readme.md                ← Full documentation
├── 📖 CHANGES_SUMMARY.md       ← What was cleaned up
│
├── 🛠️  view_events.py           ← Tool: Plot data
├── 🛠️  waterfall_stream.py      ← Tool: Animate data
├── 🛠️  event_movie.py           ← Tool: Create videos
│
├── 📋 .env_example             ← Copy to .env, set your folder
├── 📋 pyproject.toml           ← Dependencies (don't edit)
│
├── 📂 event_lists/             ← Pre-made event lists (ready to use)
│   ├── beaver_fiber_event_list_nat.csv
│   ├── beaver_fiber_event_list_droog.csv
│   ├── beaver_fiber_event_list_ijken.csv
│   └── beaver_fiber_event_list_vochtig.csv
│
├── 📂 channel_fiber_map/       ← Geographic coordinates (for maps)
│
├── 📂 outputs/                 ← Your plots, videos go here
│
└── 📂 src/beaverfiber/         ← Python library (don't edit)
```

## ⚡ Common Tasks

### "I want to plot one test"
```python
# Edit view_events.py
TEST_IDS = ["TST-001"]
MEASUREMENTS = ["1e stap"]
# Run: pixi run view-events
```

### "I want to watch data play back"
```python
# Edit waterfall_stream.py
START_DATETIME = "2026-10-12 11:01:00"
STOP_DATETIME = "2026-10-12 11:06:00"
# Run: pixi run waterfall-stream
# Press Space to pause/resume, close to stop
```

### "I want to create a map video"
```python
# Edit event_movie.py
TEST_IDS = ["TST-001"]
MEASUREMENTS = ["1e stap"]
WRITE_MP4 = True
# Run: pixi run event-movie
# Check outputs/ for .mp4 file
```

## 🆘 Something Not Working?

**Check these:**

1. Did you run `pixi install`? → Run it again
2. Is `.env` missing or wrong? → Copy `.env_example` to `.env` and edit it
3. Can't find your HDF5 files? → Check the path in `.env` is correct
4. Getting "No valid time" error? → Check your CSV file (measurement time might be empty)

👉 **For more help:** See [QUICK_REFERENCE.md](QUICK_REFERENCE.md) troubleshooting section

## 🎓 For Students

You're using this tool as part of your coursework. The repository has been simplified specifically for you:

- ✅ **No confusing development files** – clean and focused
- ✅ **Clear documentation** – multiple starting points
- ✅ **Easy setup** – 15 minutes from download to first plot
- ✅ **Pre-made data** – event lists included, ready to go

**Next step:** Open [STUDENT_START_HERE.md](STUDENT_START_HERE.md) for a 5-minute introduction.

## 📖 Documentation Map

```
START HERE
    ↓
STUDENT_START_HERE.md (5 min introduction)
    ↓
Choose your next step:
├─ QUICK_REFERENCE.md (need to look something up fast)
├─ readme.md (want full details)
└─ CHANGES_SUMMARY.md (want to know what was cleaned)
```

---

**Made simple for students. Happy plotting! 🚀**
