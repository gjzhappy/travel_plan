# Travel Plan — OpenCode 智能旅行规划 Skill

这是可离线稳定演示的 OpenCode Workspace。它把模糊语言理解和体验判断限制在
两个 Agent 内，把候选选择、时间、地图、餐饮、酒店、行李、预算与校验全部放在
可测试的 Python 代码中。

## 架构与职责

```text
/travel → Requirement Agent → JSON/Requirement validation
        → Qdrant semantic top-k → SQLite facts → weather/code shortlist
        → Route Planner → Map → Meal Planner → Hotel Optimizer
        → Hard Validator → Code Repair → Review Agent
        → Review JSON → Requirement Agent → validated refined intent
        → scoped Replanner (最多两轮) → Validator/Review → Renderer → trip_state/version
```

只有两个 Agent：Requirement Agent 理解“用户要什么”并将 Review JSON 翻译为约束，Review Agent 只发现疲劳、
重复、偏好缺失等体验问题。它们均无权规划或修改路线。Route Planner 使用小规模
排列搜索和明确 score，把优先级、区域、交通、等待、开放/最晚入场、游玩时长、
紧凑度、重复类型真正纳入计算；因此不会产生不可审计的 LLM 猜测。

| 层 | 关键文件 |
|---|---|
| OpenCode 合同 | `.opencode/skills/travel-planner/SKILL.md`、`.opencode/commands/travel.md` |
| 两 Agent | `.opencode/agents/`、`src/travel_plan/agents/` |
| 召回/事实/API | `src/travel_plan/retrieval/` |
| 路线/餐饮/酒店 | `src/travel_plan/planning/` |
| 校验/修复 | `src/travel_plan/validation/` |
| 增量状态 | `src/travel_plan/conversation/` |
| 编排 | `src/travel_plan/workflow.py` |

## 使用 `/travel`

在 OpenCode 打开此 Workspace：

```text
/travel 上海4天，2个成人1个孩子，喜欢科技、自然和夜景，不要太赶，公共交通优先，少走路，住宿灵活，最多换一次，必须去迪士尼。
/travel 第二天晚饭改成火锅
/travel 第二天不要去博物馆
/travel 第一天满意，不要再改
```

Command 强制进入 Skill SOP。直接运行同一引擎也可以：

```bash
PYTHONPATH=src python -m travel_plan.main '上海4天，喜欢科技和夜景，必须去迪士尼' --trip-id trip_001
```

## 数据初始化、Mock 与 Qdrant

```bash
pip install -r requirements.txt
python scripts/init_db.py
PYTHONPATH=src pytest -q
PYTHONPATH=src python scripts/demo.py
```

`data/travel.db` 是从 `data/seed/*.json` 生成的运行时文件，不进入 Git。初始化脚本会
创建 `data/`、完整重建 POI、餐厅、酒店和攻略表并执行 SQLite integrity check，可以
安全重复运行。CLI 和 Demo 在数据库不存在时也会自动执行相同的 Seed → SQLite 初始化，
所以新 clone 的仓库不依赖预置数据库。

SQLite 是票价、坐标、时长、预约和结构化营业时间的最终事实源。Qdrant 只保存语义
描述/攻略切片并返回 similarity。默认 `mock_mode: true` 使用内存语义 fallback、
`MockMapClient` 和 `MockWeatherClient`，测试及 Demo 无网络依赖。语义层通过
`EmbeddingProvider` 边界使用 `BAAI/bge-small-zh-v1.5`，模型首次缓存后可完全离线、
批量且确定性地生成归一化向量。POI 事实仍在 SQLite；自然语言攻略只进入 Qdrant。

首次联网下载模型并生成 POI + 35 条攻略的向量制品：

```bash
python scripts/build_embeddings.py --download
```

后续断网运行不加 `--download`；也可用 `--model-path /path/to/cached/model` 显式指定本地模型。
向量制品位于被忽略的 `data/generated/`。启动 Qdrant：

```bash
docker run --rm -p 6333:6333 qdrant/qdrant
```

然后运行 `python scripts/build_qdrant.py`，将制品写入兼容原代码的
`shanghai_travel_poi` collection。collection 以 `type=poi/guide` 区分 81 个 POI 与攻略，
攻略命中会展开其 `poi_ids`，再由 SQLite 完成事实补全；Qdrant 不负责最终路线选择。
`qdrant_storage/` 等本地向量存储同样是生成物，不进入 Git。
真实地图/天气配置应在
私有配置中提供 API key 与 provider endpoint，并实例化 `RealMapClient` /
`RealWeatherClient`；示例参数集中在 `config/config.example.yaml`，切勿提交密钥。

## Demo 与测试

```bash
PYTHONPATH=src python scripts/demo.py
PYTHONPATH=src pytest -q
```

### Web Demo

Web 界面是现有 Travel Engine 的轻量展示层，不引入新 Agent，也不改变规划、校验、
状态或事件链路。启动后访问 `http://127.0.0.1:8000`：

```bash
PYTHONPATH=src python -m travel_plan.web.server
```

在首页用自然语言描述需求，生成后可查看按日时间轴、上海路线示意地图、景点与餐饮、
住宿和预算。折叠的“为什么这样安排”使用规划结果中的事实和评分生成确定性展示文案；
普通界面不暴露 Agent、检索、Validator 和 Event Trace 等技术细节。Web API 为
`POST /api/plans`，请求体格式为 `{"request": "...", "trip_id": "可选"}`。

测试覆盖解析、开放/特殊日期/最晚入场、语义与事实职责、天气降权、路线 score、
餐饮偏好/预算/绕路、酒店 KEEP/CHANGE、行李闭环、硬校验、Review、四种 Scope、锁定、
持久版本及首次规划—餐饮修改—按日修改—锁定的端到端链路。

## 状态、证据与限制

每个行程的观察性事件以 JSONL 追加到 `data/state/<trip_id>/events.jsonl`（自定义
`--state-dir` 时位于对应目录）。事件包含行程与父/当前 plan version、顺序号、事件类型、
执行者和最小决策详情，可追踪 Agent、Review、Replan、Validator 和版本保存。事件写入是
best-effort：失败只记录 warning，不会改变规划、校验或持久化流程。
`TraceReader` 可只读解析该文件，并通过 `timeline()` 或 `render()` 生成按追加顺序排列的
可解释时间线；缺少 trace 时返回空时间线，损坏的事件则报告其文件与行号。Reader 不调用
Agent、Planner 或 Validator，也不修改行程状态。

每次调用写 `data/state/<trip_id>/version_N.json` 和 `current.json`；这些运行时状态被
`.gitignore` 排除。锁定、拒绝项和拒绝
分类均为显式状态，不依赖聊天记忆。结果区分 SQLite 事实、Qdrant 语义、mock/真实 API
观测、算法计算和 Review 判断。当前演示只内置上海数据；真实 provider adapter 刻意要求
部署方配置 endpoint。中文规则解析器用于完全离线演示，OpenCode 运行时可用同一严格
Schema 的 Requirement Agent 提升自由表达覆盖率，但不能越过确定性工作流。
