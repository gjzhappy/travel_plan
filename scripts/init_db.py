#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from travel_plan.retrieval.database import initialize_database

DB = ROOT / "data/travel.db"


def main() -> None:
    path = initialize_database(DB, ROOT / "data/seed")
    print(f"initialized {path} from {ROOT / 'data/seed'}")


if __name__ == "__main__":
    main()
