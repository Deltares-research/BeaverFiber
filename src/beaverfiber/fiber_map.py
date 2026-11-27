"""Place DAS channels on the map (RD New) and upsample them along the cable."""

import sqlite3
import struct
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import sparse


@dataclass
class FiberMap:
    channels: np.ndarray  # HDF5 channel IDs that have an RD position.
    chainage: np.ndarray  # Metres along the as-built line, per channel.
    line: np.ndarray  # As-built line vertices (n, 2) in RD metres.
    line_chainage: np.ndarray  # Metres along the as-built line, per vertex.
    srs: tuple  # gpkg_spatial_ref_sys row, copied into the output GeoPackage.

    def position(self, chainage: np.ndarray) -> np.ndarray:
        """RD x/y at the given metres along the as-built line."""
        return np.stack((np.interp(chainage, self.line_chainage, self.line[:, 0]),
                         np.interp(chainage, self.line_chainage, self.line[:, 1])), axis=-1)


@dataclass
class UpsampledFiber:
    columns: np.ndarray  # Window columns that are used (mapped channels).
    weights: sparse.csr_matrix  # (points, len(columns)): linear interpolation along the cable.
    channel: np.ndarray  # Nearest HDF5 channel ID per point.
    fiber_m: np.ndarray  # HDF5 fiber distance per point.
    segments: np.ndarray  # (points, 3, 2): short line around each point, in RD metres.

    def interpolate(self, values: np.ndarray) -> np.ndarray:
        """(time, window channels) -> (time, points) in one sparse matrix product."""
        return np.asarray(self.weights @ values[:, self.columns].T).T.astype(np.float32)


def read_geometry(blob: bytes) -> np.ndarray:
    """GeoPackage point/linestring blob -> (n, 2) coordinates."""
    envelope = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}[(blob[3] >> 1) & 7]
    wkb = blob[8 + envelope:]
    order = "<" if wkb[0] == 1 else ">"
    kind = struct.unpack(order + "I", wkb[1:5])[0] % 1000
    if kind == 1:
        return np.frombuffer(wkb[5:21], order + "f8").reshape(1, 2)
    if kind != 2:
        raise ValueError(f"Unsupported geometry type {kind}")
    count = struct.unpack(order + "I", wkb[5:9])[0]
    return np.frombuffer(wkb[9:9 + 16 * count], order + "f8").reshape(count, 2)


def load_fiber_map(path: str | Path) -> FiberMap:
    """Read the mapped channels (das_channels) and the as-built line (fiber_asbuilt)."""
    with closing(sqlite3.connect(Path(path))) as connection:
        rows = connection.execute(
            "SELECT channel, chainage_m FROM das_channels WHERE rd_x IS NOT NULL AND chainage_m IS NOT NULL "
            "ORDER BY channel"
        ).fetchall()
        (blob,) = connection.execute("SELECT geom FROM fiber_asbuilt").fetchone()
        (srs_id,) = connection.execute(
            "SELECT srs_id FROM gpkg_geometry_columns WHERE table_name = 'das_channels'"
        ).fetchone()
        srs = connection.execute("SELECT * FROM gpkg_spatial_ref_sys WHERE srs_id = ?", (srs_id,)).fetchone()
    if not rows:
        raise ValueError(f"No mapped channels in {path}")
    channels, chainage = np.array(rows).T
    line = read_geometry(blob).copy()
    line_chainage = np.concatenate(([0.0], np.cumsum(np.hypot(*np.diff(line, axis=0).T))))
    return FiberMap(channels.astype(int), chainage, line, line_chainage, srs)


def _ranges(values: np.ndarray) -> str:
    """[0, 2, 4, 10] -> '0-4, 10' for readable warnings."""
    if not len(values):
        return ""
    breaks = np.flatnonzero(np.diff(values) != np.median(np.diff(values)) if len(values) > 1 else []) + 1
    parts = np.split(values, breaks)
    return ", ".join(f"{part[0]}" if len(part) == 1 else f"{part[0]}-{part[-1]}" for part in parts)


def upsample_fiber(fiber_map: FiberMap, channels: np.ndarray, distances: np.ndarray, factor: int) -> UpsampledFiber:
    """Insert factor-1 points between neighbouring mapped channels, following the as-built line.

    Channels without an RD position are left out with a warning; the cable is split there.
    """
    if int(factor) != factor or factor < 1:
        raise ValueError("UPSAMPLE_FACTOR must be a whole number of at least 1")
    factor = int(factor)
    mapped = np.isin(channels, fiber_map.channels)
    if not mapped.any():
        raise ValueError("None of the selected channels has an RD position in the fiber map")
    if not mapped.all():
        print(f"Warning: no RD position for channel IDs {_ranges(channels[~mapped])}; they are left out of the map.")
    columns = np.flatnonzero(mapped)
    in_map = np.searchsorted(fiber_map.channels, channels[columns])
    chainage = fiber_map.chainage[in_map]

    rows, cols, weights, point_chainage, point_fiber, point_channel, segments = [], [], [], [], [], [], []
    gaps = (np.diff(columns) != 1) | (np.diff(in_map) != 1)
    runs = np.split(np.arange(len(columns)), np.flatnonzero(gaps) + 1)
    offset = 0
    for run in runs:
        steps = np.arange((len(run) - 1) * factor + 1)
        left = np.minimum(steps // factor, max(len(run) - 2, 0))
        fraction = steps / factor - left if len(run) > 1 else np.zeros(1)
        right = np.minimum(left + 1, len(run) - 1)
        rows += [offset + steps, offset + steps]
        cols += [run[left], run[right]]
        weights += [1 - fraction, fraction]
        along = chainage[run[left]] * (1 - fraction) + chainage[run[right]] * fraction
        point_chainage.append(along)
        point_fiber.append(distances[columns[run[left]]] * (1 - fraction) + distances[columns[run[right]]] * fraction)
        point_channel.append(channels[columns[run[np.where(fraction < 0.5, left, right)]]])
        if len(along) > 1:
            middle = (along[:-1] + along[1:]) / 2
            start, end = np.concatenate(([along[0]], middle)), np.concatenate((middle, [along[-1]]))
        else:
            start, end = along - 1.0, along + 1.0
        segments.append(fiber_map.position(np.stack((start, along, end), axis=1)))
        offset += len(steps)

    matrix = sparse.csr_matrix(
        (np.concatenate(weights), (np.concatenate(rows), np.concatenate(cols))), shape=(offset, len(columns)),
    )
    return UpsampledFiber(
        columns, matrix, np.concatenate(point_channel), np.concatenate(point_fiber), np.concatenate(segments),
    )
