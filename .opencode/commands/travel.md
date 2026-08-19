---
description: Create or incrementally modify a deterministic travel plan
agent: build
---

Load and follow the `travel-planner` skill contract without skipping any mandatory stage.
Pass the complete raw command arguments unchanged to its Python entry point. Reuse the
active trip id for modifications so locked/rejected items and versions are authoritative.

User request: `$ARGUMENTS`

