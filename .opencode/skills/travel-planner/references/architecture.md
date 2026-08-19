# Architecture

`Requirement Agent → schema → Qdrant → SQLite → filters → Route/Meal/Hotel code →
Hard Validator/Code Repair → Review Agent → scoped code replan → render/state/version`.

Evidence is typed by source: SQLite facts, Qdrant semantic recommendations, map/weather
observations, algorithm calculations, and Review Agent experience judgments.

