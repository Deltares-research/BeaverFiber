import csv
import runpy
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import h5py
import numpy as np

from beaverfiber import plot_events
from beaverfiber.plot_event import Event, Window, bandpass_window, extract_window, mean_psd, read_events, scan_recordings, waterfall_display


class EventPlotTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.start = datetime(2026, 10, 12, tzinfo=timezone.utc)
        self.dt = 0.0016
        self.channels = np.array([0, 2, 4])
        self.distances = np.array([0.0, 2.04, 4.08])
        self.counts = np.arange(1250 * 3, dtype=np.int16).reshape(1250, 3)
        self.event = Event("IJK-027", [self.start + timedelta(seconds=1)],
                           self.start + timedelta(seconds=0.2), self.start + timedelta(seconds=1.8))

    def recording(self, name, offset, counts):
        path = self.folder / name
        with h5py.File(path, "w") as handle:
            handle["data"] = counts
            handle["header/time"] = self.start.timestamp() + offset
            handle["header/dt"] = self.dt
            handle["header/channels"] = self.channels
            handle["header/missingSamples"] = np.array([], dtype=np.int32)
            handle["cableSpec/sensorDistances"] = self.distances
        return path

    def recordings(self, second_start=1.0):
        self.recording("first.hdf5", 0, self.counts[:625])
        self.recording("second.hdf5", second_start, self.counts[625:])
        return scan_recordings(self.folder)

    def test_full_window_matches_source_and_has_no_duplicate_boundary(self):
        window = extract_window(self.recordings(), self.event)
        np.testing.assert_array_equal(window.counts, self.counts[125:1125])
        np.testing.assert_array_equal(window.channels, self.channels)
        np.testing.assert_allclose(np.diff(window.timestamps), self.dt, rtol=0, atol=3e-7)
        self.assertEqual(len(window.sources), 2)
        self.assertEqual(window.timestamps[0], self.event.start.timestamp())
        self.assertLess(window.timestamps[-1], self.event.end.timestamp())

    def test_actual_channel_ids_and_inclusive_range(self):
        recordings = self.recordings()
        selected = extract_window(recordings, self.event, channels=[4, 0])
        np.testing.assert_array_equal(selected.channels, [0, 4])
        np.testing.assert_array_equal(selected.counts, self.counts[125:1125, :][:, [0, 2]])
        interval = extract_window(recordings, self.event, channel_range=[2, 4])
        np.testing.assert_array_equal(interval.counts, self.counts[125:1125, 1:])
        with self.assertRaisesRegex(ValueError, "not recorded"):
            extract_window(recordings, self.event, channels=[1])

    def test_gap_and_overlap_are_rejected(self):
        for offset in (1.01, 0.99):
            with self.subTest(offset=offset):
                with self.assertRaisesRegex(ValueError, "Gap or overlap"):
                    extract_window(self.recordings(offset), self.event)

    def test_missing_start_coverage_is_rejected(self):
        self.recording("second.hdf5", 1, self.counts[625:])
        with self.assertRaisesRegex(ValueError, "complete requested window"):
            extract_window(scan_recordings(self.folder), self.event)

    def test_unreadable_file_outside_window_can_be_skipped(self):
        self.recordings()
        (self.folder / "broken.hdf5").write_bytes(b"incomplete HDF5 file")
        with self.assertRaisesRegex(ValueError, "Cannot index"):
            scan_recordings(self.folder)
        with self.assertWarnsRegex(RuntimeWarning, "Skipping unreadable recording"):
            recordings = scan_recordings(self.folder, skip_unreadable=True)
        np.testing.assert_array_equal(extract_window(recordings, self.event).counts, self.counts[125:1125])

    def test_skipped_file_inside_window_still_rejects_missing_coverage(self):
        self.recordings()
        (self.folder / "second.hdf5").write_bytes(b"incomplete HDF5 file")
        with self.assertWarnsRegex(RuntimeWarning, "Skipping unreadable recording"):
            recordings = scan_recordings(self.folder, skip_unreadable=True)
        with self.assertRaisesRegex(ValueError, "complete requested window"):
            extract_window(recordings, self.event)

    def test_mapping_change_and_declared_missing_samples_are_rejected(self):
        recordings = self.recordings()
        with h5py.File(self.folder / "second.hdf5", "r+") as handle:
            handle["header/channels"][1] = 3
        with self.assertRaisesRegex(ValueError, "mapping changed"):
            extract_window(recordings, self.event)
        self.recordings()
        with h5py.File(self.folder / "second.hdf5", "r+") as handle:
            del handle["header/missingSamples"]
            handle["header/missingSamples"] = [2]
        with self.assertRaisesRegex(ValueError, "Missing samples"):
            extract_window(recordings, self.event)

    def test_both_date_formats_and_id_alias(self):
        path = self.folder / "events.csv"
        for date in ("2026-10-12", "12-10-2026"):
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=["Test-ID", "Date", "1e meting", "2e meting"])
                writer.writeheader()
                writer.writerow({"Test-ID": "IJK-027", "Date": date, "1e meting": "11:36:35", "2e meting": "11:36:55"})
            event = read_events(path, ["IJK27"], 10, 10)[0]
            self.assertEqual(event.start.isoformat(), "2026-10-12T11:36:25+00:00")
            self.assertEqual(event.end.isoformat(), "2026-10-12T11:37:05+00:00")

    def test_psd_averages_power_not_signals(self):
        timestamps = np.arange(6250) * self.dt
        signal = np.sin(2 * np.pi * 25 * timestamps).astype(np.float32)
        counts = np.column_stack([signal, -signal])
        window = Window(counts, timestamps, self.channels[:2], self.distances[:2], self.dt, [])
        frequencies, power = mean_psd(window)
        self.assertAlmostEqual(frequencies[np.argmax(power)], 25)
        self.assertAlmostEqual(float(np.sum(power) * (frequencies[1] - frequencies[0])), 0.5, places=5)
        self.assertTrue(np.all(np.isfinite(power)))

    def test_channel_normalization_preserves_samples_and_psd(self):
        counts = np.array([[0, 1, 10], [0, -3, -30], [0, 4, 40], [0, -8, -80]], dtype=np.int16)
        original = counts.copy()
        window = Window(counts, np.arange(4) * self.dt, self.channels, self.distances, self.dt, [])
        frequencies, power = mean_psd(window)
        display, limit, label = waterfall_display(counts, normalize_channels=True)
        np.testing.assert_array_equal(counts, original)
        np.testing.assert_allclose(display[:, 1], display[:, 2])
        np.testing.assert_allclose(display[:, 1], [0.2, -0.6, 0.8, -1.6])
        np.testing.assert_array_equal(display[:, 0], 0)
        self.assertTrue(np.all(np.isfinite(display)))
        self.assertEqual(limit, 3)
        self.assertIn("normalized", label)
        frequencies_after, power_after = mean_psd(window)
        np.testing.assert_array_equal(frequencies_after, frequencies)
        np.testing.assert_array_equal(power_after, power)

    def test_raw_waterfall_scaling_is_unchanged(self):
        counts = np.array([[0, -32768], [0, 32767]], dtype=np.int16)
        display, limit, label = waterfall_display(counts)
        np.testing.assert_array_equal(display, counts)
        self.assertAlmostEqual(limit, float(np.percentile(np.abs(counts.astype(np.float32)), 99)))
        self.assertIn("Raw counts", label)

    def test_bandpass_preserves_passband_and_suppresses_outside_frequencies(self):
        times = np.arange(12500) * self.dt
        signal = np.sin(2 * np.pi * 20 * times) + np.sin(2 * np.pi * 100 * times) + 3
        counts = np.column_stack([signal, signal * 2, np.zeros_like(signal)])
        original = counts.copy()
        window = Window(counts, times, self.channels, self.distances, self.dt, [])
        self.assertIs(bandpass_window(window, None), window)
        filtered = bandpass_window(window, (10, 40))
        interior = slice(1250, -1250)
        expected = np.sin(2 * np.pi * 20 * times[interior])
        self.assertLess(float(np.sqrt(np.mean((filtered.counts[interior, 0] - expected) ** 2))), 0.02)
        np.testing.assert_allclose(filtered.counts[:, 1], filtered.counts[:, 0] * 2)
        np.testing.assert_array_equal(filtered.counts[:, 2], 0)
        np.testing.assert_array_equal(window.counts, original)
        self.assertIs(filtered.timestamps, window.timestamps)
        frequencies, raw_power = mean_psd(window)
        _, filtered_power = mean_psd(filtered)
        index = int(np.argmin(np.abs(frequencies - 100)))
        self.assertLess(filtered_power[index], raw_power[index] * 0.001)

    def test_bandpass_rejects_invalid_cutoffs_and_short_windows(self):
        window = Window(self.counts, np.arange(len(self.counts)) * self.dt, self.channels, self.distances, self.dt, [])
        for cutoffs in ((0, 40), (40, 10), (10, 312.5), (10, float("nan")), (10,)):
            with self.subTest(cutoffs=cutoffs), self.assertRaises(ValueError):
                bandpass_window(window, cutoffs)
        short = Window(self.counts[:2], np.arange(2) * self.dt, self.channels, self.distances, self.dt, [])
        with self.assertRaisesRegex(ValueError, "too short"):
            bandpass_window(short, (10, 40))

    def test_amsterdam_event_times_convert_to_utc_with_daylight_saving(self):
        path = self.folder / "events.csv"
        for date, expected in (("12-10-2026", "2026-10-12T09:06:15+00:00"), ("12-01-2026", "2026-01-12T10:06:15+00:00")):
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=["Test-ID", "Date", "1e meting", "2e meting"])
                writer.writeheader()
                writer.writerow({"Test-ID": "IJK-002", "Date": date, "1e meting": "11:06:15", "2e meting": "11:06:45"})
            event = read_events(path, ["IJK-002"], 2, 2, event_timezone="Europe/Amsterdam")[0]
            self.assertEqual(event.measurements[0].isoformat(), expected)
            self.assertEqual((event.end - event.start).total_seconds(), 34)

    def test_public_workflow_reads_env_and_saves_figure(self):
        self.recordings()
        events_path = self.folder / "events.csv"
        with events_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["Test-ID", "Date", "1e meting", "2e meting"])
            writer.writeheader()
            writer.writerow({"Test-ID": "IJK-027", "Date": "12-10-2026", "1e meting": "00:00:01", "2e meting": "00:00:01"})
        env_path = self.folder / ".env"
        env_path.write_text('data_folder="."\nevent_list="events.csv"\n', encoding="utf-8")
        with patch("matplotlib.pyplot.show") as show:
            outputs = plot_events(
                ["IJK27"], env_file=env_path, before_seconds=0.8, after_seconds=0.8,
                event_timezone="UTC",
                channel_range=(0, 2), output_dir=self.folder / "plots", show=False,
            )
            show.assert_not_called()
        self.assertEqual(outputs, [self.folder / "plots" / "IJK-027_waterfall_psd.png"])
        from matplotlib.image import imread

        pixels = imread(outputs[0])
        self.assertGreater(float(pixels.std()), 0.01)

    def test_public_workflow_validates_inputs_before_reading_files(self):
        for arguments in (
            {"test_ids": []},
            {"test_ids": "IJK27"},
            {"test_ids": ["IJK27"], "before_seconds": -1},
            {"test_ids": ["IJK27"], "channels": [0], "channel_range": (0, 2)},
            {"test_ids": ["IJK27"], "channel_range": (4, 0)},
        ):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                plot_events(**arguments)

    def test_manual_window_overrides_ids_and_padding_without_event_csv(self):
        self.recordings()
        env_path = self.folder / ".env"
        env_path.write_text('data_folder="."\n', encoding="utf-8")
        with patch("beaverfiber.plot_event.plot_window") as plot:
            outputs = plot_events(
                ["NOT-IN-CSV"], env_file=env_path,
                time_window_utc=("2026-10-12 00:00:00.2", "2026-10-12T00:00:01.8Z"),
                before_seconds=-1, after_seconds=-1,
                channel_range=(0, 2), output_dir=self.folder / "plots", show=False,
            )
        event, window, output, show = plot.call_args.args
        self.assertEqual(event.start, self.event.start)
        self.assertEqual(event.end, self.event.end)
        self.assertEqual(event.measurements, [])
        np.testing.assert_array_equal(window.counts, self.counts[125:1125, :2])
        self.assertEqual(outputs, [output])
        self.assertTrue(output.name.startswith("manual_"))
        self.assertFalse(show)

    def test_manual_datetimes_are_converted_to_utc(self):
        self.recordings()
        env_path = self.folder / ".env"
        env_path.write_text('data_folder="."\n', encoding="utf-8")
        with patch("beaverfiber.plot_event.plot_window") as plot:
            plot_events(
                env_file=env_path, output_dir=self.folder,
                time_window_utc=(datetime.fromisoformat("2026-10-12T02:00:00.2+02:00"), self.event.end),
                show=False,
            )
        self.assertEqual(plot.call_args.args[0].start, self.event.start)

    def test_invalid_manual_windows_are_rejected(self):
        for window in (
            ("2026-10-12T00:00:01Z", "2026-10-12T00:00:01Z"),
            ("2026-10-12T00:00:02Z", "2026-10-12T00:00:01Z"),
            ("bad timestamp", "2026-10-12T00:00:01Z"),
            (None, "2026-10-12T00:00:01Z"),
            ("2026-10-12T00:00:01Z",),
        ):
            with self.subTest(window=window), self.assertRaises(ValueError):
                plot_events(time_window_utc=window)

    def test_user_script_passes_inputs_to_package(self):
        script = Path(__file__).resolve().parents[1] / "view_events.py"
        with patch("beaverfiber.plot_events") as workflow:
            inputs = runpy.run_path(str(script), run_name="__main__")
        workflow.assert_called_once_with(
            test_ids=inputs["TEST_IDS"], time_window_utc=inputs["TIME_WINDOW_UTC"],
            event_timezone=inputs["EVENT_TIMEZONE"],
            before_seconds=inputs["BEFORE_SECONDS"], after_seconds=inputs["AFTER_SECONDS"],
            channels=inputs["CHANNELS"], channel_range=inputs["CHANNEL_RANGE"], env_file=inputs["ENV_FILE"],
            normalize_channels=inputs["NORMALIZE_CHANNELS"],
            bandpass_hz=inputs["BANDPASS_HZ"],
            output_dir=inputs["OUTPUT_DIR"], show=inputs["SHOW_PLOTS"],
        )


if __name__ == "__main__":
    unittest.main()