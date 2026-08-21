#!/usr/bin/env python3
"""Download/cache BGE once, then build a portable knowledge-point artifact."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from travel_plan.retrieval.embedding_provider import BGEEmbeddingProvider
from travel_plan.retrieval.qdrant_repository import qdrant_points

parser = argparse.ArgumentParser()
parser.add_argument("--model-path", help="Cached model directory; defaults to the Hugging Face cache")
parser.add_argument("--download", action="store_true", help="Allow the initial model download")
parser.add_argument("--output", type=Path, default=ROOT / "data/generated/qdrant_points.json")
args = parser.parse_args()
provider = BGEEmbeddingProvider(args.model_path, offline=not args.download)
pois = json.loads((ROOT / "data/source/shanghai_pois.json").read_text(encoding="utf-8"))
guides = json.loads((ROOT / "data/source/shanghai_guides.json").read_text(encoding="utf-8"))
points = qdrant_points(pois, guides, provider)
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(points, ensure_ascii=False), encoding="utf-8")
print(f"wrote {len(points)} vectors ({provider.dimension} dimensions) to {args.output}")
