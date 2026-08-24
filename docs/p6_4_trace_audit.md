# P6.4 Trace taxonomy and evidence audit

The append-only JSONL trace is execution truth. The workflow graph and timeline are
read-only projections; itinerary fields never backfill an executed state.

## Stable taxonomy

| Event | Producer | Required facts | Graph node | User label | Repeats | Can fail |
|---|---|---|---|---|---|---|
| `WORKFLOW_STARTED` | workflow | version identity | input | 提交旅行需求 | no/version | no |
| `STAGE_STARTED/COMPLETED/FAILED: REQUIREMENT` | requirement agent | stage, duration on terminal event | requirement | 理解旅行需求 | no/version | yes |
| `STAGE_STARTED/COMPLETED/FAILED: RETRIEVAL` | retrieval service | stage, candidate count and duration on completion | retrieval | 查找合适地点 | yes | yes |
| `STAGE_STARTED/COMPLETED/FAILED: PLANNER` | planning engine | stage, scope and duration on completion | planner | 编排行程框架 | yes | yes |
| `STAGE_STARTED/COMPLETED/FAILED: ROUTE_PLANNING` | route planner | stage and measured duration | route | 安排行程顺序 | yes | yes |
| `STAGE_STARTED/COMPLETED/FAILED: MEAL_PLANNING` | meal planner | stage and measured duration | meal | 安排餐饮 | yes | yes |
| `STAGE_STARTED/COMPLETED/FAILED: HOTEL_PLANNING` | hotel optimizer | stage and measured duration | hotel | 安排住宿衔接 | yes | yes |
| `STAGE_STARTED/COMPLETED/FAILED: VALIDATOR` | hard validator | stage, pass result and measured duration | validator | 可行性检查 | yes | yes |
| `STAGE_STARTED` + `REVIEW_COMPLETED` | review agent | review number, result, issues, measured duration | review | 行程体验审核 | yes | yes/result |
| `STAGE_STARTED/COMPLETED/FAILED: REQUIREMENT_REFINEMENT` | requirement agent | iteration, scope and measured duration | requirement_refinement | 根据审核调整需求 | yes | yes |
| `STAGE_STARTED/COMPLETED/FAILED: SCOPED_REPLAN` | replanner | iteration, scope, target and measured duration | scoped_replanner | 调整部分行程 | yes | yes |
| `STAGE_STARTED/COMPLETED/FAILED: HARD_VALIDATION` | hard validator | iteration, result and measured duration | feedback_validator | 再次检查 | yes | yes |
| `STAGE_STARTED/COMPLETED/FAILED: FINAL_VALIDATION` | hard validator | result and measured duration | feedback_validator | 最终检查 | no/version | yes |
| `PLAN_VERSION_SAVED` | state manager | version identity/change | output | 保存方案 | no/version | yes (no event) |

`VALIDATOR_PASSED/BLOCKED` remain checkpoint facts. New stage lifecycle writes use only
`STARTED`, `COMPLETED`, and `FAILED`. `AGENT_HEARTBEAT` is streaming telemetry: it updates
one running presentation node and is neither persisted nor included in measured stage duration.
Architecture-only nodes (`facts`, `constraints`, and `repair` when no explicit lifecycle event
exists) stay available/pending.

## Review loop and history

A passing review proceeds to final validation and persistence. A failing review is followed by
explicit, iteration-numbered refinement, scoped replan, post-replan validation, and the next
review. The reader filters by `trip_id + plan_version`; therefore version snapshots cannot share
executed state. Both normal plan responses and historical version responses include a graph
rebuilt from that version's persisted events.

## Clean deterministic demo audit (2026-08-24 UTC)

A clean `shanghai_family_trip` run produced version 1 with 40 append-only facts. The actual
terminal stages were: requirement 103.736 ms; retrieval 9.095 ms; route planning 1868.516 ms;
hotel planning 0.127 ms; meal planning 3.669 ms; planning 1873.047 ms; initial validation
1.089 ms; review iterations 1/2/3 at 0.927/1.031/0.915 ms; refinement iterations 1/2 at
1.285/1.032 ms; scoped replan iterations 1/2 at 553.327/586.507 ms; post-replan validation
iterations 1/2 at 1.232/1.261 ms; and final validation 1.191 ms. Every terminal stage projects
to the same completed/failed state in graph and timeline. All three reviews recorded an advisory
result (`passed=false`); the hard final validation passed and only then was version 1 persisted.
These are execution measurements, not the deterministic UI minimum-visible durations.

## Copy boundary

| Internal term | User-facing term |
|---|---|
| Requirement Agent | 需求理解 |
| Retrieval | 查找合适地点 |
| Fact Enrichment | 核对地点信息 |
| Route Planner | 安排行程顺序 |
| Meal Planner | 安排餐饮 |
| Hotel Optimizer | 安排住宿衔接 |
| Hard Validator | 可行性检查 |
| Review Agent | 行程体验审核 |
| Requirement Refinement | 根据审核调整需求 |
| Scoped Replanner | 调整部分行程 |
| Final Validator | 最终检查 |
| Persist | 保存方案 |

Technical names, event types, internal IDs, and raw payloads remain confined to expandable
technical details or APIs. Decision explanations omit route claims when recorded transport
metrics are absent; workflow execution is not presented as a reason for a travel decision.
