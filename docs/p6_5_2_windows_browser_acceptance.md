# P6.5.2 Windows Browser Final Acceptance

Audit date: 2026-08-24 UTC.

## Acceptance basis

This report does **not** substitute Linux, API, static inspection, or automated regression
results for the required real Windows browser rehearsal. The available execution environment
is a Linux container with no Chrome, Edge, Chromium, Firefox, Windows `cmd.exe`, display, or
interactive desktop. Consequently `scripts/start_demo.bat` cannot be double-clicked here and
neither required viewport can be rendered.

No browser observations, screenshots, or timings have been fabricated. No P0/P1 was observed
in a Windows browser because the required environment was unavailable; equally, the absence
of P0/P1 cannot be established. The final gate therefore remains **NO-GO — BROWSER VALIDATION
PENDING**. This is an acceptance-environment blocker, not a newly discovered business-code
defect.

## Environment

| Item | Required | Actually available |
| --- | --- | --- |
| OS | Windows, version recorded | Ubuntu 24.04.4 LTS, Linux x86_64 |
| Browser | Chrome or Edge | None discovered |
| Resolution | 1366×768 and 1920×1080 | Not renderable |
| Runtime | `agent-mode = deterministic` | Repository deterministic mode is available, but the Windows browser run was not started |
| Launcher | Double-click `scripts/start_demo.bat` | File present; native execution unavailable because `cmd.exe` and a Windows desktop are absent |
| Python | Discoverable from BAT | CPython 3.14.4 available on Linux; BAT discovery untested |
| Node | Automated syntax check | v24.15.0 |

## Startup

**NOT EXECUTED / FAIL (mandatory gate).** The required double-click launch chain—CMD display,
initialization feedback, server readiness, and browser opening only after readiness—cannot be
observed on this host.

Actual duration: **not recorded; run not executed**.

This must not be replaced by `python server.py`, a prestarted server, the Linux launcher, or
an API request.

## Fixed Demo

**NOT EXECUTED / FAIL (mandatory browser gate).** `shanghai_family_trip` was not selected and
started through a real Windows browser in this acceptance run. No claim is made about result
reveal, 上海迪士尼乐园 rendering, or end-to-end browser stability.

## Planning Pacing

Actual duration: **not recorded; run not executed**.

Verdict: **NOT EXECUTED / FAIL**. The required visible 8–12 second presentation and the
requirement → retrieval → route → meals/hotel → validation → review progression remain to be
timed by a human. Engine or test duration is not presentation duration.

## Review Advisory

Actual browser behavior: **not observed**.

Verdict: **NOT EXECUTED / FAIL**. A Windows browser must confirm that completed review stages
with an advisory business result appear as successful execution with optimization advice,
never as `FAILED`/error, while leaving review policy unchanged.

## Timeline

The required manual DAY1–DAY4 browser inspection was not performed. Attractions must be
transcribed from the final visible plan during the Windows run rather than copied from an API
or an earlier rehearsal.

* DAY1: **not recorded**
* DAY2: **not recorded**
* DAY3: **not recorded**
* DAY4: **not recorded**

Verdict: **NOT EXECUTED / FAIL**. Chronology, meals, afternoon activity, hotel return, gaps,
overlap, and cross-day ordinary-attraction uniqueness are pending visual inspection.

## Map

* Hotel H / 人民广场酒店 closure: **not observed**.
* Dense markers ④/⑤ (including the targeted fixture when needed): **not observed**.
* Timeline → marker highlight: **not observed**.
* Marker → timeline highlight and stable identity after visual offset: **not observed**.

Verdict: **NOT EXECUTED / FAIL**.

## Decision Evidence

No browser evidence cards were sampled in this run. The mandatory samples below must be read
in the browser and cross-checked against the facts belonging to that exact plan version.

| Coverage | Claim | Source fact | Verdict |
| --- | --- | --- | --- |
| must_visit | Not recorded | Must compare canonical POI identity and requirement facts | NOT EXECUTED |
| route order | Not recorded | Must compare visible route order and stable POI identities | NOT EXECUTED |
| time constraint | Not recorded | Must compare arrival/opening/latest-entry values | NOT EXECUTED |
| meal detour | Not recorded | Must compare the displayed number with `detour_min` | NOT EXECUTED |
| hotel | Not recorded | Must compare hotel identity, switch facts, and daily closure | NOT EXECUTED |

Verdict: **FAIL (mandatory sampling incomplete)**. Generic field narration such as “已记录开放
时间” is not acceptable evidence, and no numerical or factual PASS is claimed without the
corresponding visible plan fact.

## Workflow Evidence

* Trace: **not inspected through the accepted browser flow**.
* Graph: **not inspected through the accepted browser flow**.
* Execution Timeline: **not inspected through the accepted browser flow**.
* Requirement, Route Planning, Review, Scoped Replan, Final Validation agreement: **pending**.
* Completed graph has no active/running node: **pending**.
* Executed and unexecuted nodes/edges match actual events: **pending**.
* Review lifecycle `completed` remains distinct from business result `advisory`: **pending**.
* Displayed technical durations originate from Event Trace rather than minimum dwell: **pending**.

Verdict: **NOT EXECUTED / FAIL**.

## Refresh

**NOT EXECUTED / FAIL.** F5 reconstruction of the final plan, timeline, map, decision evidence,
workflow graph, and execution timeline was not tested. In particular, no claim is made that
the graph avoids returning to `WAITING_START` in Chrome or Edge.

Actual duration: **not recorded; run not executed**.

## Version 1 / Version 2

**NOT EXECUTED / FAIL.** A browser DAY2 modification was not submitted, and V1 ↔ V2 switching
was not inspected for immutable itineraries or graph, timeline, and decision-evidence
isolation.

Version-change duration: **not recorded; run not executed**.

## Scoped Replan Uniqueness

**NOT EXECUTED / FAIL.** Browser copy indicating DAY2-only work, the real scoped graph path,
and absence of ordinary POIs already used on unaffected days remain pending. Automated
regression coverage passing below does not replace this P6.5.1 browser acceptance gate.

## Free Input

Input to use: `我想带孩子在上海玩3天，喜欢博物馆和科技馆，不想太累。`

**NOT EXECUTED / FAIL.** Three-day output, requirement/route/validator/review behavior, and
absence of fixed-demo UI assumptions remain pending in a Windows browser.

## Alias

Input to use: `我想在上海玩3天，上海迪士尼一定要去。`

**NOT EXECUTED / FAIL.** The browser must confirm that canonical `上海迪士尼乐园` appears in
the itinerary.

## Failure UX

Input to use: `上海完全不存在测试景点ABC一定要去`.

**NOT EXECUTED / FAIL.** Friendly fail-closed rendering, absence of internal exception terms,
and absence of a saved successful plan remain pending.

## 1366×768

**NOT EXECUTED / FAIL.** CTA accessibility, timeline/map size, evidence, graph, version control,
technical details, overflow, and tooltip bounds were not rendered.

## 1920×1080

**NOT EXECUTED / FAIL.** Maximum content width and timeline/map/graph readability were not
rendered.

## Five-Minute Demo

Actual duration: **not recorded; rehearsal not executed**.

**FAIL (mandatory gate).** Startup, planning presentation, route walkthrough, evidence,
workflow, refresh, and version change have no actual browser timings. Estimated values and
automated engine timings are intentionally omitted.

## Findings

### P0

None newly observed. This statement does not mean P0-clear: the required environment was not
available to exercise the gates that could reveal a P0.

### P1

None newly observed. This statement does not mean P1-clear for the same reason.

### P2 / P3

None recorded; no browser presentation was available to assess minor visual findings.

### Acceptance blocker

The host is not Windows and provides no real browser or interactive display. Therefore the
mandatory launcher, visual, interaction, refresh, viewport, and timed-rehearsal evidence is
missing. The correct action is to run the full checklist on the target Windows competition
machine, not to change business code.

## Automated Regression

These checks establish only the current automated baseline:

| Check | Result |
| --- | --- |
| `pytest -q` | PASS — 157 passed, 1 skipped |
| `python -m compileall -q src scripts` | PASS |
| `node --check src/travel_plan/web/static/app.js` | PASS |
| `git diff --check` | PASS before this report was added; rerun after the final edit |

No business or presentation code was modified in P6.5.2.

## Windows completion record

The operator must replace every **not recorded/not executed** field above with direct evidence
from one uninterrupted clean Windows rehearsal. Record these actual values (never estimates):

| Segment | Actual time |
| --- | --- |
| Startup | pending |
| Planning presentation | pending |
| Route walkthrough | pending |
| Evidence | pending |
| Workflow | pending |
| Refresh | pending |
| Version change | pending |
| Total | pending |

Minimum completion sequence:

1. On the target Windows machine, ensure no demo server is prestarted; double-click
   `scripts/start_demo.bat` and record Windows version, Chrome/Edge version, startup behavior,
   and actual duration.
2. Run the fixed case from its visible CTA; time planning and inspect DAY1–DAY4, canonical
   Disney exactly once, hotel H closure, review advisories, evidence, graph, trace timeline,
   and true stage durations.
3. At 1366×768 and 1920×1080, inspect all critical controls and content. Exercise the dense
   marker fixture and both directions of timeline/map selection.
4. Refresh v1, create a DAY2-scoped v2, switch versions repeatedly, and confirm immutable,
   isolated itinerary/workflow/timeline/evidence plus cross-day POI uniqueness.
5. Run the free, alias, and unknown-must-visit inputs; then perform and time the complete
   narrated five-minute rehearsal.
6. If a P0/P1 is found, capture Finding / Evidence / Root cause, make only the minimum allowed
   fix, and repeat this entire sequence from BAT startup. P2/P3 findings are documentation-only.
7. Change the verdict to GO only after every mandatory item passes with direct browser
   evidence and no P0/P1 remains.

## Known Limitations

These are retained and are not blockers:

* The current product scope is Shanghai only.
* POIs, hotels, and restaurants come from an offline example library.
* Weather, transport, reservation, and crowd information use mock providers.
* There is no real reservation or booking execution.
* There is no live crowd information.
* Alias coverage cannot include every colloquial expression.
* The heuristic planner is not an industrial-grade vehicle-routing solver.
* Deterministic runtime is the default demo mode.
* OpenCode Agent Runtime requires an additional environment.

## FINAL VERDICT

# NO-GO

**BROWSER VALIDATION PENDING.** `PROJECT STATUS = FROZEN` and `READY FOR COMPETITION DEMO`
cannot truthfully be declared until the full real-Windows Chrome/Edge rehearsal passes at both
required resolutions with actual timings and no P0/P1.

No further feature development is authorized by this report. The next action is acceptance
execution on the required Windows environment; code changes are permitted only for a P0/P1
demonstrated there and must be followed by the complete rehearsal again.
