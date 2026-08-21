#!/usr/bin/env python3
"""Recreate and populate the Shanghai semantic knowledge collection."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from qdrant_client import QdrantClient, models
from travel_plan.retrieval.qdrant_repository import COLLECTION_NAME

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://localhost:6333")
parser.add_argument("--input", type=Path, default=ROOT / "data/generated/qdrant_points.json")
args = parser.parse_args()
points = json.loads(args.input.read_text(encoding="utf-8"))
if not points:
    raise SystemExit("embedding artifact is empty")
client = QdrantClient(url=args.url)
client.recreate_collection(COLLECTION_NAME, vectors_config=models.VectorParams(size=len(points[0]["vector"]), distance=models.Distance.COSINE))
client.upsert(COLLECTION_NAME, points=[models.PointStruct(**point) for point in points], wait=True)
print(f"collection={COLLECTION_NAME}; upserted={len(points)}")
