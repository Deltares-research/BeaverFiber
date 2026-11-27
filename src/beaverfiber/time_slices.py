"""Pick time slices and write them as a QGIS temporal GeoPackage layer."""

import re
import sqlite3
import struct
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import quoteattr

import numpy as np

from .fiber_map import FiberMap, UpsampledFiber


def select_slices(values: np.ndarray, timestamps: np.ndarray, dt: float, interval_s: float):
    """Every n-th true sample (no averaging); returns (slices, times, actual interval)."""
    step = max(1, round(interval_s / dt))
    if abs(step * dt - interval_s) > 1e-6:
        print(f"Note: SLICE_INTERVAL_S {interval_s:g} s is not a multiple of the sample interval "
              f"{dt:g} s; using {step * dt:g} s.")
    return values[::step], timestamps[::step], step * dt


def layer_name(*parts: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9]", "_", "_".join(parts))).strip("_")


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _linestring_blobs(segments: np.ndarray, srs_id: int) -> list[bytes]:
    """GeoPackage blobs (no envelope, little endian) for (n, vertices, 2) line segments."""
    header = b"GP\x00\x01" + struct.pack("<i", srs_id) + b"\x01" + struct.pack("<II", 2, segments.shape[1])
    coordinates = np.ascontiguousarray(segments, dtype="<f8").reshape(len(segments), -1)
    return [header + row.tobytes() for row in coordinates]


def style_qml(envelope: bool, limit: float) -> str:
    """QGIS style: colour by amplitude with fixed limits, and temporal settings for the Temporal Controller."""
    if envelope:
        color = f"ramp_color('Viridis', scale_linear(\"amplitude\", 0, {limit:.6g}, 0, 1))"
    else:
        color = f"ramp_color('RdBu', scale_linear(\"amplitude\", {-limit:.6g}, {limit:.6g}, 1, 0))"
    return f"""<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.44.9-Solothurn" styleCategories="Symbology|Temporal">
  <temporal enabled="1" mode="2" limitMode="0" startField="time_start" endField="time_end"
            startExpression="" endExpression="" durationField="" durationUnit="min" fixedDuration="0" accumulate="0">
    <fixedRange><start></start><end></end></fixedRange>
  </temporal>
  <renderer-v2 type="singleSymbol" forceraster="0" symbollevels="0" enableorderby="0" referencescale="-1">
    <symbols>
      <symbol type="line" name="0" alpha="1" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleLine" enabled="1" locked="0" pass="0">
          <Option type="Map">
            <Option type="QString" name="capstyle" value="flat"/>
            <Option type="QString" name="joinstyle" value="round"/>
            <Option type="QString" name="line_color" value="128,128,128,255"/>
            <Option type="QString" name="line_style" value="solid"/>
            <Option type="QString" name="line_width" value="1.6"/>
            <Option type="QString" name="line_width_unit" value="MM"/>
          </Option>
          <data_defined_properties>
            <Option type="Map">
              <Option type="QString" name="name" value=""/>
              <Option type="Map" name="properties">
                <Option type="Map" name="outlineColor">
                  <Option type="bool" name="active" value="true"/>
                  <Option type="QString" name="expression" value={quoteattr(color)}/>
                  <Option type="int" name="type" value="3"/>
                </Option>
              </Option>
              <Option type="QString" name="type" value="collection"/>
            </Option>
          </data_defined_properties>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
  <layerGeometryType>1</layerGeometryType>
</qgis>
"""


def _prepare(connection: sqlite3.Connection, srs: tuple) -> None:
    connection.execute("PRAGMA application_id = 1196444487")  # 'GPKG'
    connection.execute("PRAGMA user_version = 10400")
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS gpkg_spatial_ref_sys (
            srs_name TEXT NOT NULL, srs_id INTEGER PRIMARY KEY, organization TEXT NOT NULL,
            organization_coordsys_id INTEGER NOT NULL, definition TEXT NOT NULL, description TEXT);
        CREATE TABLE IF NOT EXISTS gpkg_contents (
            table_name TEXT NOT NULL PRIMARY KEY, data_type TEXT NOT NULL, identifier TEXT UNIQUE,
            description TEXT DEFAULT '', last_change DATETIME NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            min_x DOUBLE, min_y DOUBLE, max_x DOUBLE, max_y DOUBLE, srs_id INTEGER,
            CONSTRAINT fk_gc_r_srs_id FOREIGN KEY (srs_id) REFERENCES gpkg_spatial_ref_sys(srs_id));
        CREATE TABLE IF NOT EXISTS gpkg_geometry_columns (
            table_name TEXT NOT NULL, column_name TEXT NOT NULL, geometry_type_name TEXT NOT NULL,
            srs_id INTEGER NOT NULL, z TINYINT NOT NULL, m TINYINT NOT NULL,
            CONSTRAINT pk_geom_cols PRIMARY KEY (table_name, column_name),
            CONSTRAINT fk_gc_tn FOREIGN KEY (table_name) REFERENCES gpkg_contents(table_name),
            CONSTRAINT fk_gc_srs FOREIGN KEY (srs_id) REFERENCES gpkg_spatial_ref_sys(srs_id));
        CREATE TABLE IF NOT EXISTS layer_styles (
            id INTEGER PRIMARY KEY AUTOINCREMENT, f_table_catalog TEXT(256), f_table_schema TEXT(256),
            f_table_name TEXT(256), f_geometry_column TEXT(256), styleName TEXT(30), styleQML TEXT,
            styleSLD TEXT, useAsDefault BOOLEAN, description TEXT, owner TEXT(30), ui TEXT(30),
            update_time DATETIME DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
    """)
    defaults = [
        ("Undefined cartesian SRS", -1, "NONE", -1, "undefined", None),
        ("Undefined geographic SRS", 0, "NONE", 0, "undefined", None),
        ("WGS 84 geodetic", 4326, "EPSG", 4326, 'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,'
         '298.257223563]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433],AUTHORITY["EPSG","4326"]]', None),
        tuple(srs),
    ]
    connection.executemany("INSERT OR IGNORE INTO gpkg_spatial_ref_sys VALUES (?, ?, ?, ?, ?, ?)", defaults)
    connection.execute("INSERT OR IGNORE INTO gpkg_contents (table_name, data_type, identifier) "
                       "VALUES ('layer_styles', 'attributes', 'layer_styles')")


def write_time_slices(
    path: Path, layer: str, fiber_map: FiberMap, fiber: UpsampledFiber, values: np.ndarray,
    times: np.ndarray, interval_s: float, event_time: float, envelope: bool, limit: float, description: str,
) -> None:
    """One feature per (cable segment, time slice); an existing layer with the same name is replaced."""
    srs_id = int(fiber_map.srs[1])
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA journal_mode = MEMORY")
        connection.execute("PRAGMA synchronous = OFF")
        with connection:
            _prepare(connection, fiber_map.srs)
            for table in ("gpkg_geometry_columns", "gpkg_contents"):
                connection.execute(f"DELETE FROM {table} WHERE table_name = ?", (layer,))
            connection.execute("DELETE FROM layer_styles WHERE f_table_name = ?", (layer,))
            connection.execute(f'DROP TABLE IF EXISTS "{layer}"')
            connection.execute(f"""CREATE TABLE "{layer}" (
                fid INTEGER PRIMARY KEY AUTOINCREMENT, geom LINESTRING, segment INTEGER, channel INTEGER,
                fiber_m REAL, time_start DATETIME, time_end DATETIME, t_rel_s REAL, phase TEXT, amplitude REAL)""")

            connection.execute("CREATE TEMP TABLE segment (id INTEGER PRIMARY KEY, geom BLOB, channel INTEGER, fiber_m REAL)")
            connection.executemany("INSERT INTO temp.segment VALUES (?, ?, ?, ?)", zip(
                range(len(fiber.segments)), _linestring_blobs(fiber.segments, srs_id),
                fiber.channel.tolist(), np.round(fiber.fiber_m, 3).tolist(),
            ))
            connection.execute("CREATE TEMP TABLE frame (id INTEGER PRIMARY KEY, time_start TEXT, time_end TEXT, "
                               "t_rel_s REAL, phase TEXT)")
            connection.executemany("INSERT INTO temp.frame VALUES (?, ?, ?, ?, ?)", (
                (index, _iso(time), _iso(time + interval_s), round(time - event_time, 6),
                 "noise" if time < event_time else "signal")
                for index, time in enumerate(times.tolist())
            ))
            connection.execute("CREATE TEMP TABLE amplitude (frame INTEGER, segment INTEGER, value REAL)")
            frames, segments = np.indices(values.shape)
            connection.executemany("INSERT INTO temp.amplitude VALUES (?, ?, ?)", zip(
                frames.ravel().tolist(), segments.ravel().tolist(), values.ravel().astype(float).tolist(),
            ))
            connection.execute(f"""INSERT INTO "{layer}"
                (geom, segment, channel, fiber_m, time_start, time_end, t_rel_s, phase, amplitude)
                SELECT s.geom, s.id, s.channel, s.fiber_m, f.time_start, f.time_end, f.t_rel_s, f.phase, a.value
                FROM temp.amplitude a JOIN temp.frame f ON f.id = a.frame JOIN temp.segment s ON s.id = a.segment
                ORDER BY a.frame, a.segment""")
            for table in ("segment", "frame", "amplitude"):
                connection.execute(f"DROP TABLE temp.{table}")
            connection.execute(f'CREATE INDEX "{layer}_time" ON "{layer}" (time_start, time_end)')

            x, y = fiber.segments[..., 0], fiber.segments[..., 1]
            connection.execute(
                "INSERT INTO gpkg_contents (table_name, data_type, identifier, description, min_x, min_y, max_x, "
                "max_y, srs_id) VALUES (?, 'features', ?, ?, ?, ?, ?, ?, ?)",
                (layer, layer, description, x.min(), y.min(), x.max(), y.max(), srs_id),
            )
            connection.execute("INSERT INTO gpkg_geometry_columns VALUES (?, 'geom', 'LINESTRING', ?, 0, 0)",
                               (layer, srs_id))
            connection.execute(
                "INSERT INTO layer_styles (f_table_catalog, f_table_schema, f_table_name, f_geometry_column, "
                "styleName, styleQML, styleSLD, useAsDefault, description, owner, ui) "
                "VALUES ('', '', ?, 'geom', ?, ?, '', 1, 'BeaverFiber time slices', '', '')",
                (layer, layer[:30], style_qml(envelope, limit)),
            )
    finally:
        connection.close()
    print(f"Saved layer {layer} ({values.size:,} features) in {path}")
