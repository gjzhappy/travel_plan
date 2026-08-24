"""Build the generated SQLite fact store from version-controlled JSON seeds."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from travel_plan.errors import DataUnavailableError

SEED_FILES = {
    "restaurants": "restaurants.json",
    "hotels": "hotels.json",
}

SCHEMA = """
CREATE TABLE poi(
    poi_id INTEGER PRIMARY KEY, name TEXT NOT NULL, canonical_name TEXT NOT NULL,
    aliases TEXT NOT NULL, city TEXT NOT NULL,
    district TEXT NOT NULL, lat REAL NOT NULL, lon REAL NOT NULL,
    category TEXT NOT NULL, ticket_price REAL NOT NULL,
    duration_min INTEGER NOT NULL, reservation_required INTEGER NOT NULL,
    opening_hours TEXT NOT NULL, semantic_description TEXT NOT NULL,
    outdoor INTEGER NOT NULL,
    tags TEXT NOT NULL, description TEXT NOT NULL,
    special_dates TEXT NOT NULL, latest_entry_time TEXT,
    ticket_required INTEGER NOT NULL,
    family_friendly_score INTEGER NOT NULL, night_view_score INTEGER NOT NULL,
    indoor INTEGER NOT NULL, crowd_level TEXT NOT NULL
);
CREATE TABLE restaurants(
    restaurant_id INTEGER PRIMARY KEY, name TEXT NOT NULL, city TEXT NOT NULL,
    cuisine TEXT NOT NULL, district TEXT NOT NULL, lat REAL NOT NULL,
    lon REAL NOT NULL, price_per_person REAL NOT NULL,
    opening_hours TEXT NOT NULL
);
CREATE TABLE hotels(
    hotel_id INTEGER PRIMARY KEY, name TEXT NOT NULL, city TEXT NOT NULL,
    district TEXT NOT NULL, lat REAL NOT NULL, lon REAL NOT NULL,
    nightly_price REAL NOT NULL, supports_luggage_storage INTEGER NOT NULL,
    check_in_time TEXT NOT NULL, check_out_time TEXT NOT NULL
);
CREATE TABLE guides(
    guide_id INTEGER PRIMARY KEY AUTOINCREMENT, poi_id INTEGER NOT NULL,
    city TEXT NOT NULL, semantic_description TEXT NOT NULL, text TEXT NOT NULL,
    FOREIGN KEY(poi_id) REFERENCES poi(poi_id)
);
CREATE VIEW pois AS SELECT * FROM poi;
CREATE INDEX idx_poi_city ON poi(city);
CREATE INDEX idx_restaurants_city ON restaurants(city);
CREATE INDEX idx_hotels_city ON hotels(city);
CREATE INDEX idx_guides_city ON guides(city);
"""


def _load_seed(seed_dir: Path, name: str) -> list[dict[str, Any]]:
    path = seed_dir / SEED_FILES[name]
    if not path.is_file():
        raise DataUnavailableError(f"Required seed file is missing: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataUnavailableError(f"Cannot read seed file {path}: {exc}") from exc
    if not isinstance(value, list) or not value or not all(isinstance(row, dict) for row in value):
        raise DataUnavailableError(f"Seed file must contain a non-empty JSON object array: {path}")
    return value


def _insert_rows(connection: sqlite3.Connection, table: str, rows: list[dict[str, Any]]) -> None:
    columns = list(rows[0])
    if any(set(row) != set(columns) for row in rows):
        raise DataUnavailableError(f"Inconsistent columns in {table} seed data")
    values = [
        [json.dumps(row[column], ensure_ascii=False) if column in {"opening_hours", "tags", "special_dates", "aliases"} else row[column] for column in columns]
        for row in rows
    ]
    placeholders = ",".join("?" for _ in columns)
    connection.executemany(
        f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})", values
    )


def initialize_database(database_path: str | Path, seed_dir: str | Path) -> Path:
    """Atomically rebuild all fact tables from seeds; safe to run repeatedly."""
    target = Path(database_path)
    seeds = Path(seed_dir)
    loaded = {name: _load_seed(seeds, name) for name in SEED_FILES}
    # Resolve seed symlinks so isolated demo workspaces can reuse both source folders.
    source_path = seeds.resolve().parent / "source" / "shanghai_pois.json"
    if not source_path.is_file():
        raise DataUnavailableError(f"Required source dataset is missing: {source_path}")
    try:
        source_pois = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataUnavailableError(f"Cannot read source dataset {source_path}: {exc}") from exc
    if not isinstance(source_pois, list) or not source_pois:
        raise DataUnavailableError(f"Source dataset must be a non-empty array: {source_path}")
    loaded["pois"] = [_source_poi_to_row(row) for row in source_pois]
    loaded["guides"] = [
        {"poi_id": row["poi_id"], "city": "上海",
         "semantic_description": " ".join(row["tags"]),
         "text": f'{row["name"]}：{row["description"]}'}
        for row in source_pois
    ]
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        connection = sqlite3.connect(temporary)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executescript(SCHEMA)
            for table in ("pois", "restaurants", "hotels", "guides"):
                _insert_rows(connection, "poi" if table == "pois" else table, loaded[table])
            connection.commit()
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise DataUnavailableError(f"SQLite integrity check failed: {integrity}")
        finally:
            connection.close()
        temporary.replace(target)
    except (sqlite3.Error, OSError, DataUnavailableError) as exc:
        temporary.unlink(missing_ok=True)
        if isinstance(exc, DataUnavailableError):
            raise
        raise DataUnavailableError(f"Failed to initialize {target} from {seeds}: {exc}") from exc
    return target


def _source_poi_to_row(row: dict[str, Any]) -> dict[str, Any]:
    """Translate the public source schema into the stable planner fact schema."""
    hours = {
        "weekly_hours": row["opening_hours"],
        "special_dates": row["special_dates"],
        "latest_entry_time": row["latest_entry_time"],
    }
    return {
        "poi_id": row["poi_id"], "name": row["name"],
        "canonical_name": row.get("canonical_name", row["name"]),
        "aliases": row.get("aliases", []), "city": "上海",
        "district": row["district"], "lat": row["latitude"], "lon": row["longitude"],
        "category": row["category"], "ticket_price": row["ticket_price"],
        "duration_min": row["visit_duration_min"],
        "reservation_required": int(row["reservation_required"]),
        "opening_hours": hours, "semantic_description": " ".join(row["tags"]),
        "outdoor": int(not row["indoor"]), "tags": row["tags"],
        "description": row["description"], "special_dates": row["special_dates"],
        "latest_entry_time": row["latest_entry_time"],
        "ticket_required": int(row["ticket_required"]),
        "family_friendly_score": row["family_friendly_score"],
        "night_view_score": row["night_view_score"], "indoor": int(row["indoor"]),
        "crowd_level": row["crowd_level"],
    }
