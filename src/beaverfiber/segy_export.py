"""Write the plotted samples to a SEG-Y revision 1 file (big-endian IEEE float32)."""

import struct
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .plot_event import Event, Window


def write_segy(event: Event, window: Window, counts: np.ndarray, output: Path) -> None:
    """One trace per channel; trace time zero is the first sample of the window.

    Receiver X holds the fiber distance in millimetres (coordinate scalar -1000).
    """
    samples, traces = counts.shape
    interval_us = round(window.dt * 1e6)
    if samples > 65535:
        raise ValueError("SEG-Y allows at most 65535 samples per trace; use a shorter window")
    if not 1 <= interval_us <= 65535:
        raise ValueError("SEG-Y sample interval must be 1-65535 microseconds")
    first = datetime.fromtimestamp(float(window.timestamps[0]), timezone.utc)
    offset = event.time.timestamp() - window.timestamps[0]
    lines = [
        "BEAVERFIBER DAS EXPORT",
        f"TEST-ID: {event.test_id}  MEASUREMENT: {event.measurement}",
        f"FIRST SAMPLE UTC: {first.isoformat(timespec='microseconds')}",
        f"MEASUREMENT UTC: {event.time.isoformat(timespec='microseconds')}",
        f"MEASUREMENT AT {offset:.6f} S AFTER TRACE START (NOISE BEFORE, SIGNAL AFTER)",
        "ONE TRACE PER CHANNEL; TRACE NUMBER (BYTES 13-16) = CHANNEL ID",
        "RECEIVER X (BYTES 81-84) = FIBER DISTANCE IN MM, SCALAR -1000",
        "AMPLITUDES IN COUNTS; NO NORMALIZATION OR CLIPPING",
    ]
    lines += [""] * (40 - len(lines))
    text = "".join(f"C{number:2d} {line[:76]:<76}" for number, line in enumerate(lines, 1)).encode("ascii", "replace")

    binary = bytearray(400)
    struct.pack_into(">H", binary, 16, interval_us)
    struct.pack_into(">H", binary, 20, samples)
    struct.pack_into(">H", binary, 24, 5)  # IEEE float32.
    struct.pack_into(">h", binary, 54, 1)  # Metres.
    struct.pack_into(">H", binary, 300, 0x0100)  # Revision 1.0.
    struct.pack_into(">h", binary, 302, 1)  # Fixed-length traces.

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as stream:
        stream.write(text + binary)
        for index in range(traces):
            header = bytearray(240)
            struct.pack_into(">iiii", header, 0, index + 1, index + 1, 1, int(window.channels[index]))
            struct.pack_into(">h", header, 28, 1)  # Seismic data trace.
            struct.pack_into(">h", header, 70, -1000)  # Coordinate scalar.
            struct.pack_into(">i", header, 80, round(window.distances[index] * 1000))
            struct.pack_into(">h", header, 88, 1)  # Length coordinates.
            struct.pack_into(">HH", header, 114, samples, interval_us)
            struct.pack_into(">hhhhhh", header, 156, first.year, first.timetuple().tm_yday,
                             first.hour, first.minute, first.second, 4)  # UTC.
            stream.write(header)
            stream.write(np.asarray(counts[:, index], dtype=">f4").tobytes())
    print(f"Saved {output}")
