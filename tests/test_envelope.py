import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import matplotlib
import numpy as np
from scipy.signal import hilbert

from beaverfiber import plot_event

matplotlib.use("Agg")
import matplotlib.pyplot as plt


class EnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.dt = 0.01
        times = np.arange(256) * self.dt
        self.counts = np.column_stack((
            np.sin(2 * np.pi * 8 * times) + 0.3 * np.sin(2 * np.pi * 30 * times),
            2 * np.cos(2 * np.pi * 12 * times),
        ))
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.event = plot_event.Event("TST-1", "test", start + timedelta(seconds=1.28),
                                      start, start + timedelta(seconds=2.56))
        self.window = plot_event.Window(
            self.counts, start.timestamp() + times, np.array([1, 2]), np.array([10., 20.]), self.dt,
        )

    def test_processed_samples_reach_waterfall_psd_and_segy(self):
        for enabled, bandpass_hz in ((True, (5, 15)), (True, None), (False, (5, 15)), (False, None)):
            with self.subTest(envelope=enabled, bandpass_hz=bandpass_hz):
                expected = self.counts if bandpass_hz is None else plot_event.bandpass(
                    self.counts, self.dt, bandpass_hz,
                )
                if enabled:
                    expected = np.abs(hilbert(expected, axis=0))
                with patch.object(plt.Figure, "savefig"), \
                     patch("beaverfiber.segy_export.write_segy") as export, \
                     patch.object(plot_event, "waterfall_image", wraps=plot_event.waterfall_image) as image, \
                     patch.object(plot_event, "mean_psd", wraps=plot_event.mean_psd) as psd:
                    plot_event.plot_window(
                        self.event, self.window, Path("test.png"), show=False,
                        normalize_channels=False, bandpass_hz=bandpass_hz,
                        interpolation="nearest", clip_quantile=1.0, write_segy=True,
                        **({"envelope": True} if enabled else {}),
                    )
                np.testing.assert_allclose(export.call_args.args[2], expected)
                np.testing.assert_allclose(image.call_args.args[2], expected)
                np.testing.assert_allclose(np.concatenate([call.args[0] for call in psd.call_args_list]), expected)
                self.assertEqual(image.call_args.kwargs["vmin"] == 0, enabled)

    def test_plot_events_forwards_envelope(self):
        with patch.object(plot_event, "read_events", return_value=[self.event]), \
             patch.object(plot_event, "scan_recordings", return_value=[]), \
             patch.object(plot_event, "extract_window", return_value=self.window), \
             patch.object(plot_event, "plot_window") as plot:
            plot_event.plot_events(
                ["TST-1"], measurements=["test"], time_delta=timedelta(),
                noise_seconds=1, signal_seconds=1, fiber_range_m=None,
                normalize_channels=False, bandpass_hz=None, interpolation="nearest",
                clip_quantile=1.0, data_folder="data", event_list="events.csv",
                output_dir="outputs", show=False, write_segy=False, envelope=True,
            )
        self.assertTrue(plot.call_args.kwargs["envelope"])


if __name__ == "__main__":
    unittest.main()
