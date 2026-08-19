---
name: travel-planner
description: Controlled, deterministic travel planning and incremental modification workflow.
---

# Travel Planner workflow contract

For every `/travel` invocation execute every applicable stage in this exact order; the
main agent may not improvise, skip, reorder, or replace deterministic stages:

1. Parse the current request and load `trip_state` when a trip id exists.
2. Invoke **requirement-agent** with current text and existing state.
3. validate its Requirement JSON against `schemas/requirement.schema.json`.
4. run semantic Qdrant top-k retrieval.
5. join authoritative facts from SQLite (Qdrant is never a fact authority).
6. fetch weather and apply code filters/penalties.
7. form the explained POI shortlist.
8. run Python Route Planner for selection, grouping, ordering and timeline.
9. query map travel only for shortlisted route alternatives.
10. run Meal Planner and insert real lunch/dinner nodes and adjacent travel.
11. run Hotel Optimizer and, when changing, insert the luggage lifecycle.
12. run Hard Validator unconditionally.
13. run conservative Code Repair, then validate again; unsafe failures remain explicit.
14. invoke **review-agent** unconditionally with requirement, complete plan and evidence.
15. on review failure invoke scoped Replanner (`GLOBAL`, `DAY`, `NODE`, `MEAL`), then
    the affected code planners and Hard Validator, then Review Agent again.
16. allow at most two review/replan retries; return best effort plus remaining issues.
17. render Markdown or JSON.
18. save `trip_state`.
19. save an immutable incremented `plan_version`.

Requirement Agent only understands intent. Review Agent only reports experience issues.
**Neither agent may execute the whole workflow, choose POIs/routes/hotels, call maps,
change a plan, bypass locks, or render the final guide.** All such decisions are Python.

Run the controlled entry point. It initializes the ignored SQLite database from the
version-controlled JSON seeds automatically when the database is absent:

```bash
PYTHONPATH=src python -m travel_plan.main "$ARGUMENTS" --trip-id "${TRIP_ID:-trip_default}"
```

If a stage errors, report its typed error with context. Never invent a plan to compensate.
See [architecture](references/architecture.md).
