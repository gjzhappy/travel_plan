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
`MockMapClient` 和 `MockWeatherClient`，测试及 Demo 无网络依赖。生产环境可启动 Qdrant：

```bash
docker run --rm -p 6333:6333 qdrant/qdrant
```

然后运行 `python scripts/build_qdrant.py`，用版本管理的 `guides.json` / `pois.json`
payload 重建 collection。`qdrant_storage/` 等本地向量存储同样是生成物，不进入 Git。
真实地图/天气配置应在
私有配置中提供 API key 与 provider endpoint，并实例化 `RealMapClient` /
`RealWeatherClient`；示例参数集中在 `config/config.example.yaml`，切勿提交密钥。

## Demo 与测试

```bash
PYTHONPATH=src python scripts/demo.py
PYTHONPATH=src pytest -q
```

测试覆盖解析、开放/特殊日期/最晚入场、语义与事实职责、天气降权、路线 score、
餐饮偏好/预算/绕路、酒店 KEEP/CHANGE、行李闭环、硬校验、Review、四种 Scope、锁定、
持久版本及首次规划—餐饮修改—按日修改—锁定的端到端链路。

## 状态、证据与限制

每次调用写 `data/state/<trip_id>/version_N.json` 和 `current.json`；这些运行时状态被
`.gitignore` 排除。锁定、拒绝项和拒绝
分类均为显式状态，不依赖聊天记忆。结果区分 SQLite 事实、Qdrant 语义、mock/真实 API
观测、算法计算和 Review 判断。当前演示只内置上海数据；真实 provider adapter 刻意要求
部署方配置 endpoint。中文规则解析器用于完全离线演示，OpenCode 运行时可用同一严格
Schema 的 Requirement Agent 提升自由表达覆盖率，但不能越过确定性工作流。
