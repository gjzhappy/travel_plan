#!/usr/bin/env python3
"""Print/import the deterministic payload used by Qdrant or offline fallback."""
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
docs=json.loads((root/"data/seed/guides.json").read_text(encoding="utf-8"))
print(f"ready to upsert {len(docs)} semantic documents; mock mode needs no server")

