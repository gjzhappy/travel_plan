# P6.5.1 final demo blocker closure

## Root-cause audit

The original full planner consumes a `remaining` candidate list and removes selected
`poi_id` values after every day, so the initial four-day plan is unique. During review,
however, requirement refinement performs retrieval again, calls `plan_day` with that
unfiltered shortlist, and merges the replacement day into a copy of the full plan. The
scoped candidate assembly therefore had no knowledge of attraction identities already
owned by unaffected days. The duplicate was selected during scoped route planning and
became trip-wide when the replacement was merged; it was not created by initial planning
or by the merge operation itself.

The observed chain was:

| Iteration | Scope | Day | Selection source | Result |
| --- | --- | --- | --- | --- |
| Initial | GLOBAL | 1–4 | initial offline retrieval | unique `poi_id` values |
| Review 1 | DAY | 2 | fresh scoped retrieval / route planning | replacement merged |
| Review 2 | DAY | 2 | fresh scoped retrieval / route planning | replacement merged |
| Review 3 | — | — | advisory review, then final validation | no third replan |

Before this closure, that path could select Shanghai Science and Technology Museum
(`1028`) and Century Park (`1059`) on day 2 even though day 1 already owned those stable
identities.

## Closure behavior

For DAY and NODE planning, Python now derives `protected_poi_ids` exclusively from
out-of-scope attraction nodes. Retrieval candidates with those stable identities are
removed before route planning. NODE scope additionally protects unaffected attractions
on the same day. MEAL scope does not assemble attraction candidates, and GLOBAL planning
continues to use the complete new shortlist rather than excluding the old plan.

A resolved must-visit is passed into a scoped day only when its `poi_id` is currently
placed inside the affected scope. Thus an unaffected-day Disney remains protected and is
not re-injected, while replanning the Disney-owning day keeps the hard constraint. Alias
text is used only during resolution; uniqueness uses `poi_id`.

The hard validator is the final, non-repairing backstop. It emits
`duplicate_trip_poi` when one attraction `poi_id` occurs on multiple days. Hotel,
luggage, and meal nodes are outside this check. Code repair has no handler that deletes a
duplicate-trip node.

## Clean deterministic rehearsal

The database, state, and logs were removed before reseeding. The fixed
`shanghai_family_trip` completed with three advisory reviews and two DAY 2 scoped
replans:

| Day | `poi_id` | Canonical name |
| --- | ---: | --- |
| 1 | 1028 | 上海科技馆 |
| 1 | 1059 | 世纪公园 |
| 1 | 1046 | 上海迪士尼乐园 |
| 2 | 1001 | 外滩 |
| 2 | 1027 | 上海自然博物馆 |
| 2 | 1002 | 东方明珠广播电视塔 |
| 2 | 1045 | 浦东美术馆 |
| 2 | 1004 | 金茂大厦88层观光厅 |
| 3 | 1008 | 世博文化公园 |
| 3 | 1042 | 上海世博会博物馆 |
| 3 | 1056 | 上海植物园 |
| 3 | 1051 | 锦江乐园 |
| 3 | 1067 | 长风公园 |
| 4 | 1031 | 上海历史博物馆 |
| 4 | 1003 | 上海中心大厦上海之巅 |
| 4 | 1037 | 上海铁路博物馆 |
| 4 | 1050 | 上海动物园 |
| 4 | 1073 | 前滩太古里 |

Every pairwise ordinary-attraction intersection was empty. Review behavior was not
changed: reviews 1 and 2 remained advisory and triggered DAY 2 replans; review 3 remained
advisory and flowed to the passing final hard-validation gate.

## Status and Windows user browser rehearsal checklist

**AUTOMATED BLOCKERS CLEARED — BROWSER VALIDATION PENDING.** The remaining blocker is
the user-side Windows browser rehearsal. Do not declare GO until every item below passes.

- [ ] Double-click `scripts/start_demo.bat` and open the fixed 上海亲子四日游 demo.
- [ ] Repeat at 1366×768 and 1920×1080.
- [ ] Confirm visible planning lasts roughly 8–12 seconds and all key stages appear.
- [ ] Confirm review advisories are not presented as ERROR.
- [ ] Confirm hotel marker H and dense markers 4/5 are visible, and timeline ↔ marker
  highlighting works in both directions.
- [ ] Confirm Day 1–Day 4 timelines render normally and no ordinary attraction repeats
  across days.
- [ ] Inspect at least five decision-evidence entries.
- [ ] Confirm the completed graph remains visible, executed edges are green, unexecuted
  edges are gray, and no node remains running.
- [ ] Refresh and confirm graph and timeline restoration.
- [ ] Modify Day 2 and confirm v1/v2 remain isolated.
- [ ] Enter an unknown must-visit and confirm a user-friendly fail-closed result.
- [ ] Complete the full five-minute rehearsal, including pacing and map interaction.

Only after both resolutions, dense markers, map interaction, pacing, refresh, version
isolation, and the five-minute rehearsal all pass may the final verdict become GO.

## Architecture confirmation

No agent, LLM, prompt, route score, transport burden policy, hotel/luggage policy,
optimizer, canonical identity behavior, POI-specific rule, or UI behavior changed. The
candidate decision and validator guard are deterministic Python and use stable `poi_id`.
