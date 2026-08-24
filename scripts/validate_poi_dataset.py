#!/usr/bin/env python3
"""Validate the canonical Shanghai POI source without network access."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/source/shanghai_pois.json"
REQUIRED = {
    "poi_id", "name", "canonical_name", "aliases", "category", "tags", "description", "latitude", "longitude",
    "district", "visit_duration_min", "opening_hours", "special_dates",
    "latest_entry_time", "ticket_required", "ticket_price", "reservation_required",
    "family_friendly_score", "night_view_score", "indoor", "crowd_level",
}
CATEGORIES = {"城市地标", "历史文化", "博物馆", "亲子景点", "自然公园", "夜景商业", "小众特色"}


def validate(rows: list[dict]) -> None:
    if not 50 <= len(rows) <= 100:
        raise ValueError("dataset must contain 50-100 POIs")
    if len({row.get("poi_id") for row in rows}) != len(rows) or len({row.get("name") for row in rows}) != len(rows):
        raise ValueError("poi_id and name must be unique")
    for row in rows:
        missing = REQUIRED - set(row)
        if missing:
            raise ValueError(f'{row.get("name", "unknown")}: missing {sorted(missing)}')
        if row["category"] not in CATEGORIES:
            raise ValueError(f'{row["name"]}: unsupported category')
        if not (30.6 <= row["latitude"] <= 31.9 and 120.8 <= row["longitude"] <= 122.2):
            raise ValueError(f'{row["name"]}: coordinates outside Shanghai bounds')
        if not 1 <= row["family_friendly_score"] <= 5 or not 1 <= row["night_view_score"] <= 5:
            raise ValueError(f'{row["name"]}: scores must use the 1-5 scale')
        if row["crowd_level"] not in {"low", "medium", "high"}:
            raise ValueError(f'{row["name"]}: invalid crowd_level')
    missing_categories = CATEGORIES - {row["category"] for row in rows}
    if missing_categories:
        raise ValueError(f"missing categories: {sorted(missing_categories)}")


if __name__ == "__main__":
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    validate(data)
    print(f"validated {len(data)} Shanghai POIs across {len(CATEGORIES)} categories")
