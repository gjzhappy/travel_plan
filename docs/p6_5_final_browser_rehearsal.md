# P6.5 Final Browser Rehearsal

Audit date: 2026-08-24 UTC.

This audit deliberately distinguishes HTTP/trace inspection from browser validation. The
container has no Chrome, Chromium, Edge, Firefox, Playwright, Selenium, or Pyppeteer, and
`webbrowser.open()` returned false. Therefore P6.5 cannot pass in this environment. The
status is **BROWSER VALIDATION PENDING** and the competition verdict remains **NO-GO**.

## 1. Environment

| Item | Observed environment |
|---|---|
| OS | Ubuntu 24.04.4 LTS, Linux x86_64 |
| Browser | None available; automatic browser opening reported `Browser could not be opened automatically` |
| Resolution | 1366×768 and 1920×1080 could not be rendered |
| Python | CPython 3.14.4 |
| Node | v24.15.0 |
| Runtime mode | Deterministic Offline Agent; offline data; mock transport/weather/reservation/crowd providers |
| Launcher | `bash scripts/start_demo.sh --agent-mode deterministic`; Windows `scripts/start_demo.bat` could only be inspected/tested, not double-clicked on Linux |
| URL / port | `http://localhost:8000`, port 8000 |

No browser screenshots were created because doing so without a browser would be fabricated
evidence.

## 2. Startup Audit

**Automated result:** PASS for the Linux launcher, but Windows/browser completion remains
pending. Before each post-fix run, `data/travel.db`, `data/state`, and `logs` were removed.
No old server was reused.

Observed chain:

1. The launcher printed its banner and environment feedback immediately.
2. Python 3.14.4 passed the version check.
3. A clean SQLite database was seeded and reported 81 POIs.
4. The BGE embedding configuration and deterministic runtime were reported.
5. The server became ready before the launcher attempted to open the browser.
6. Browser opening failed non-fatally and the launcher printed the URL.

The service status endpoint independently reported `data_mode=offline` and all external
providers as `mock`. There was no stale-port conflict. The native Windows CMD display,
path handling, and browser launch remain unobserved in this Linux container.

## 3. Fixed Demo Audit

| Area | Automated observation | Verdict |
|---|---|---|
| Requirement | `shanghai_family_trip` completed from a clean database in 3.585 s engine time | PASS (API) |
| Must Visit | `上海迪士尼乐园` appeared once in the final itinerary after the P0 parser/scoped-replan fixes | PASS |
| Planning | Four days, hotel context, meals, route facts, and 40 trace events returned | PASS (API) |
| Validator | Explainability referenced trace event 38, `FINAL_GATE`, `PASSED`, with no issues | PASS |
| Review | Three `REVIEW_COMPLETED` events had `status=COMPLETED`; the final business result remained advisory (`passed=false`) | PASS after presentation fix |
| Result | HTTP 201 with a persisted v1 snapshot | PASS (API) |

The clean run exposed and then verified three minimum fixes:

* explicit `必须包含…` and `…一定要去` phrases are retained as must-visit requirements;
* a scoped replan of day 2/3 no longer re-resolves and duplicates a whole-trip must-visit;
* `PLAN_GENERATED` completes the planner node, while review advice is displayed as a
  completed review rather than a failed execution.

A remaining presentation/experience concern is that scoped review replans can introduce
POIs already present on another day (for example 上海科技馆/世纪公园 on days 1 and 2,
and 世博文化公园 on days 2 and 3). This is recorded as an unresolved P1 and was not
hidden by the successful hard validator.

## 4. Timeline Audit

The following is API-level timeline inspection, not a visual DOM audit.

| Day | Observed schedule | Transport | Finding |
|---|---|---:|---|
| DAY 1 | 09:00 上海科技馆; 10:24 世纪公园; lunch 11:37; 13:23–17:23 上海迪士尼乐园; dinner 18:15; hotel return 19:46 | 161 min | Chronological, afternoon activity, both meals, hotel closure; elevated but under the configured hard gate |
| DAY 2 | 09:00 上海科技馆; 10:24 世纪公园; lunch 11:37; three afternoon attractions; dinner 17:30; hotel return 18:57 | 131 min | Chronological and closed; repeats two day-1 attractions (P1) |
| DAY 3 | 09:00 世博文化公园; 10:25 上海世博会博物馆; lunch 11:39; three afternoon attractions; dinner 17:30; hotel return 19:04 | 145 min | Chronological and closed; repeats 世博文化公园 from day 2 (P1) |
| DAY 4 | 09:00 上海历史博物馆; 10:29 上海中心; lunch 11:49; three afternoon attractions; dinner 18:12; hotel return 19:39 | 167 min | Chronological and closed; elevated transport |

No time reversal, missing meal, all-morning day, or 3–4 hour unexplained gap was found in
the fixed scenario. The 161/131/145/167 minute totals differ from the old 100/146/159/129
baseline because the fixed demo now actually honors and schedules its declared must-visit.
No transport scoring or policy was tuned.

## 5. Map Audit

| Check | API/static-contract observation | Browser verdict |
|---|---|---|
| Hotel H | Every day contained a 人民广场酒店 departure and return; route DTOs exposed H endpoints/closure edges | Data PASS; visual pending |
| Dense markers | Each route node had a stable `route_id`, `node_sequence`, and marker label | Visual collision check pending |
| Interaction | The static implementation contains timeline/marker identity wiring | Click behavior pending |
| Route closure | Every daily route returned to 人民广场酒店; no daily checkout/checkin was emitted | Data PASS; visual pending |

The current fixed route did not contain the historical 徐汇滨江/西岸美术馆 pair. A real
browser must therefore run the targeted dense-marker fixture before GO.

## 6. Decision Evidence Audit

Five representative claims were compared with the returned structured evidence:

| Claim | Structured evidence | Verdict |
|---|---|---|
| 上海迪士尼乐园 is explicitly required | `must_visit=[上海迪士尼乐园]`, canonical POI 1046 | PASS |
| Day 1 sequence is 上海科技馆 → 世纪公园 → 上海迪士尼乐园 | `route_order` and evidence POI IDs 1028, 1059, 1046 | PASS |
| 上海迪士尼乐园 arrival 13:23 meets latest entry 21:00 | constraint fact records arrival 13:23 and latest entry 21:00 | PASS |
| 黄浦火锅餐厅6 adds about 18 minutes between 世纪公园 and 上海迪士尼乐园 | meal evidence records `detour_min=18` and the same previous/next nodes | PASS |
| Day 1 starts/returns at 人民广场酒店 without a switch | hotel evidence records `switch=false`, hotel ID 3001; timeline contains both endpoints | PASS |
| Day 3 lunch detour is about 13 minutes | meal evidence records `detour_min=13` | PASS |

The sampled explanations answered why and did not invent live data. Visual disclosure,
readability, and click-to-expand behavior remain pending.

## 7. Review Loop UX

The trace contains exactly three successfully executed review stages whose business result
was advisory. Reviews 1 and 2 were followed by requirement refinement, day-scoped replan,
and hard validation; review 3 was followed by final validation and persistence.

The first rehearsal found a P1 presentation defect: the graph marked advisory reviews as
`failed`, left requirement refinement `running`, and left the planner `running` after output
was saved. The minimal mapper fix now produces:

* Review: `completed`, not red/failed;
* Requirement refinement: `completed` when its lifecycle event completes;
* Planner: `completed` on the real `PLAN_GENERATED` event;
* Final graph: zero running and zero failed nodes;
* Business copy: `方案已通过硬约束校验，仍有体验建议`.

This confirms at the DTO/API layer that `ReviewResult.passed=false` is not represented as an
execution failure. A browser must still confirm actual color, icon, and visible copy.

## 8. Workflow Evidence Audit

* **Trace:** v1 contained 40 ordered events and ended with final validation pass plus
  `PLAN_VERSION_SAVED`.
* **Graph:** Requirement, retrieval, planner, route, meal, hotel, validator, review,
  requirement refinement, scoped replanner, feedback validator, and output were completed.
  Architecture-only facts, constraints, and repair stayed pending/gray.
* **Timeline:** Requirement, route planning, all three reviews, both scoped replans, and final
  validation were present with measured trace durations.
* **Refresh reconstruction surrogate:** a new GET of the persisted v1 versions resource
  reconstructed the same 40 events, graph state, and explainability payload. This verifies
  server reconstruction but is not a browser refresh.
* **Duration truth:** durations came from trace events (for example the clean route stage),
  not UI dwell timing.

## 9. Version Audit

A real day-scoped instruction — `第2天不去长风公园，换一个更适合亲子的景点` — created
v2 through the modification API.

* v1 retained 40 events and explainability `plan_version=1`.
* v2 retained its own 34 events and explainability `plan_version=2`.
* Both immutable snapshots remained available in one versions response.
* The day-2 itinerary differed between v1 and v2; event lists, graphs, and explainability
  remained version-specific.
* The trace recorded day scope and target day 2 rather than presenting a global replan.

API isolation passed. Browser version-button switching and visible non-mixing remain pending.

## 10. Failure UX

Input: `上海2天，不存在的测试景点ABC一定要去。`

Result: HTTP 422 with `暂时无法生成可行方案：无法在当前上海知识库中确认必去地点“不存在的测试景点ABC”`.
No plan was returned or persisted. This is fail-closed and does not expose a traceback or
internal exception class. Browser error-card rendering remains pending.

Free input (`我想带孩子在上海玩3天，喜欢博物馆和科技馆，不想太累。`) returned three
days without a crash. A viable full family request using `上海迪士尼一定要去` returned HTTP
201 and the canonical `上海迪士尼乐园`. A short underspecified three-day alias request can
still be rejected by the hard validator for meal feasibility; the UI correctly receives a
fail-closed response, but this is an MVP interpretation/feasibility boundary.

## 11. 1366×768 Audit

**BROWSER VALIDATION PENDING.** No claims are made about layout, horizontal overflow,
workflow graph readability, map size, hidden buttons, modal bounds, tooltip bounds, or marker
collision at 1366×768 or 1920×1080. These are mandatory before GO.

## 12. Five-Minute Rehearsal

A real narrated/browser five-minute rehearsal could not be performed. Automated engine
measurements were:

* fixed clean plan: 3.585 s;
* day-2 modification: successful, v2 persisted;
* free three-day input: about 1.6 s;
* successful full alias scenario: about 4.4 s.

The app's deterministic presentation pacing and human interaction time cannot be inferred
from engine time. The 8–12 second visible planning target and the complete 0:00–5:00 script
must be timed in a browser.

## 13. P0 / P1 / P2 Findings

| Severity | Finding | Evidence | Action |
|---|---|---|---|
| P0 fixed | Fixed demo text did not recognize `必须包含上海迪士尼乐园`, so Disney was absent | First clean rehearsal returned a successful plan without canonical Disney | Added explicit must-visit phrase extraction and regression tests; clean rerun contains canonical Disney |
| P0 fixed | Scoped replans of days 2/3 re-resolved the whole-trip must-visit and duplicated Disney | Post-parser clean run placed Disney on days 1–3 | Clear whole-trip must-visit only inside non-day-1 scoped planning copies; regression test added |
| P1 fixed | Advisory review and terminal planner/refinement nodes looked failed/running | First graph DTO had review=`failed`, planner/refinement=`running` after persistence | Corrected trace-to-presentation state mapping and added terminal trace regression coverage |
| P1 unresolved | Review-driven scoped replans can repeat other attractions across days | Fixed run repeats 上海科技馆/世纪公园 on days 1–2 and 世博文化公园 on days 2–3 | Minimal future fix: exclude POIs already used on unaffected days when constructing scoped replacement candidates, then rerun the entire rehearsal |
| Validation blocker | No browser available | No browser executable/framework; launcher could not open one | Run the checklist below on Windows with Chrome/Edge before competition freeze |
| P2 | Some transport totals are elevated (161/167 min) | Canonical daily transport metrics | Document; do not retune planner or transport policy in P6.5 |

## 14. Automated Tests

* `pytest -q` — 151 passed, 1 skipped.
* `python -m compileall -q src scripts` — passed.
* `node --check src/travel_plan/web/static/app.js` — passed.
* `git diff --check` — passed.
* Clean launcher plus HTTP/API rehearsal — passed on Linux; browser opening unavailable.

## 15. Known Limitations

* The knowledge base and product scope are Shanghai-only.
* POIs, hotels, and restaurants are offline seed data.
* Transport, weather, reservation, and crowd providers are mocks in demo mode.
* There is no real booking or reservation execution and no live crowd data.
* Deterministic runtime is the default demo; OpenCode requires a separately installed and
  configured runtime.
* Alias coverage is finite; unsupported or ambiguous mandatory places fail closed.
* Route construction is an MVP heuristic, not an industrial VRP solver.
* Scoped experience replanning can currently repeat an attraction from an unaffected day.
* Browser-specific layout, interactions, Windows launcher behavior, and presentation pacing
  remain unvalidated in this container.

## 16. Final Verdict

# NO-GO

**BROWSER VALIDATION PENDING.** The absent browser alone prevents P6.5 PASS. In addition,
the cross-day repeated-POI P1 should be resolved or explicitly accepted by the product owner
before final competition freeze. All fixed P0/P1 items passed the clean automated rerun, but
this document does not substitute API checks for visual browser evidence.

## USER_BROWSER_REHEARSAL_CHECKLIST

Run this checklist from a clean Windows competition machine using Chrome or Edge:

- [ ] Delete `data/travel.db`, `data/state`, `logs`, and temporary demo artifacts; confirm port
  8000 is unused.
- [ ] Double-click `scripts/start_demo.bat`; time CMD feedback → checks → seed → server ready →
  browser open → usable landing page.
- [ ] At both 1366×768 and 1920×1080, capture the landing page and confirm the Shanghai AI
  travel purpose, recommended case, free input, and offline-data disclosure are understood in
  ten seconds.
- [ ] Start `shanghai_family_trip` from the browser. Time visible Requirement, retrieval,
  route, meal, hotel, validator, review/refinement/replan, and final-validation stages; confirm
  total presentation pacing is 8–12 seconds and final copy says the itinerary check passed.
- [ ] Confirm all three advisory reviews look completed/advisory, never red ERROR/FAILED, and
  the graph has no stale running node after persistence.
- [ ] Inspect days 1–4 for chronology, lunch/dinner placement, afternoon activity, hotel
  departure/return, and the repeated-POI P1 documented above.
- [ ] Confirm canonical 上海迪士尼乐园 appears exactly once.
- [ ] On every map, confirm H 人民广场酒店 and the closing route. Run the dense
  徐汇滨江/西岸美术馆 fixture if those POIs are absent; separately click markers ④/⑤ and
  verify two identities.
- [ ] Click timeline → marker and marker → timeline; verify the correct identity highlights
  despite spider offsets.
- [ ] Expand “为什么这样安排？” on every day and compare at least the six claims sampled in
  this audit with the visible itinerary facts.
- [ ] Expand the workflow and technical details; verify executed paths are green, unused
  capabilities gray, trace durations truthful, and no prompts/tokens/chain-of-thought/raw IDs
  appear in the default view.
- [ ] Refresh after v1; confirm plan, graph, timeline, review loop, and decision evidence all
  reconstruct rather than returning to WAITING_START.
- [ ] Submit the day-2 modification; switch v1 ↔ v2 repeatedly and confirm itinerary, graph,
  timeline, review, and evidence never mix.
- [ ] Run the three-day museum/technology free input and a full viable family request containing
  `上海迪士尼一定要去`; confirm correct day count and canonical name.
- [ ] Submit the unknown mandatory place; confirm friendly fail-closed copy and no success plan,
  traceback, or internal exception name.
- [ ] Perform and time the complete narrated 0:00–5:00 script; capture at most landing,
  running workflow, route/map, decision evidence, final graph, and refresh-reconstructed graph.
- [ ] Only change the verdict to GO when every mandatory browser item passes and no P0 or P1
  remains.
