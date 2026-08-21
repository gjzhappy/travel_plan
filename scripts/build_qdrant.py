#!/usr/bin/env python3
"""Build the deterministic Qdrant points used by importers or offline inspection."""
import json
from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/"src"))
from travel_plan.retrieval.qdrant_repository import COLLECTION_NAME, qdrant_points

pois=json.loads((root/"data/source/shanghai_pois.json").read_text(encoding="utf-8"))
points=qdrant_points(pois)
print(f"collection={COLLECTION_NAME}; ready to upsert {len(points)} deterministic points; mock mode needs no server")
