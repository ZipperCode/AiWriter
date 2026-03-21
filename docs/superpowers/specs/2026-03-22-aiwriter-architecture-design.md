# AiWriter — AI 自动写小说系统概要设计文档

> 基于 production.md 架构设计文档，严格跟随其定义的六层架构、七Agent管线、核心引擎体系。

## 技术决策摘要

| 决策点 | 选择 | 理由 |
|--------|------|------|
| LLM Provider | OpenAI 兼容中转 API | 统一接口，灵活切换后端模型 |
| Embedding | text-embedding-3-large (1536维, API) | 部署简单，无需本地 GPU |
| Reranker | Jina Reranker v3 (API) | 与整体 API 调用策略一致 |
| 设计组织 | 按技术层次（自底向上） | 架构清晰，依赖关系一目了然 |
| 实施策略 | 先完整概要设计，再按5迭代逐步实施 | 先看全貌，再逐步推进 |

---

## 一、持久化层 (Persistence Layer)

### 1.1 PostgreSQL 17 + pgvector

- Docker 镜像：`pgvector/pgvector:pg17`
- ORM：SQLAlchemy 2.0 (async mode) + asyncpg 驱动
- 数据库迁移：Alembic
- 向量维度：1536 (对应 text-embedding-3-large)
- 向量索引策略：HNSW (m=16, ef_construction=64)

### 1.2 Redis 8

- Docker 镜像：`redis:8-alpine`
- 用途：Celery 任务 Broker / 会话缓存 / SSE 消息总线 (pub/sub)

### 1.3 核心表设计

严格遵循 production.md 4.2 节 Schema 定义。

#### 项目级表

| 表名 | 职责 | 关键字段 |
|------|------|----------|
| projects | 项目 | title, genre, status, settings |
| volumes | 分卷 | project_id, objective, climax_hint, sort_order |
| chapters | 章节 | volume_id, pov_character_id, timeline_position, status(planned/writing/draft_ready/audited/final/needs_revision) |
| drafts | 草稿 | chapter_id, content, generation_meta(JSONB), audit_score, content_embedding(vector 1536) |
| entities | 实体 | entity_type(character/location/faction/item/concept/power_system), aliases(JSONB), attributes(JSONB), locked_attributes(JSONB), knowledge_boundary(JSONB), embedding(vector 1536), confidence, source(manual/auto_extracted) |
| relationships | 实体关系 | source_entity_id→target_entity_id, relation_type, attributes(JSONB), valid_from_chapter_id, valid_to_chapter_id |
| truth_files | 10个真相文件 | file_type, content(JSONB), version, UNIQUE(project_id, file_type) |
| truth_file_history | 真相文件历史 | truth_file_id, version, content(JSONB), changed_by_chapter_id |
| scene_cards | 场景卡 | chapter_id, pov_character_id, goal, conflict, outcome, characters(JSONB), sort_order |
| hooks | 伏笔 | hook_type(foreshadow/cliffhanger/chekhov_gun), planted_chapter_id, expected_resolve_chapter, status(open/resolved/abandoned) |
| pacing_meta | 节奏元数据 | chapter_id(UNIQUE), quest_ratio, fire_ratio, constellation_ratio, highlight_count, highlight_types(JSONB), tension_level, strand_tags(JSONB) |
| audit_records | 审计记录 | chapter_id, draft_id, dimension, category(consistency/narrative/character/structure/style/engagement), score(0-10), severity(pass/warning/error/blocking), evidence(JSONB) |
| memory_entries | 章节记忆 | chapter_id, summary, embedding(vector 1536) |
| worldbook | 世界书条目 | 自由格式设定条目 |
| style_presets | 风格预设 | 写作风格模板 |
| book_rules | 本书规则 | 三层规则体系 |

#### 全局表

| 表名 | 职责 |
|------|------|
| provider_configs | 模型提供商配置 (API地址/密钥/模型名/参数) |
| usage_records | 用量追踪 (模型/token消耗/成本/时间) |
| job_runs | 任务执行记录 (Agent链路/状态/耗时) |
| workflow_presets | 工作流模板 |

### 1.4 Python 模型组织

```
backend/app/models/
├── project.py
├── volume.py
├── chapter.py
├── draft.py
├── entity.py
├── relationship.py
├── truth_file.py
├── scene_card.py
├── hook.py
├── pacing_meta.py
├── audit_record.py
├── memory_entry.py
├── worldbook.py
├── style_preset.py
├── book_rules.py
├── provider_config.py
├── usage_record.py
├── job_run.py
└── workflow_preset.py
```

统一使用 SQLAlchemy 2.0 声明式映射 (DeclarativeBase)，所有模型包含 `id (UUID)`, `created_at`, `updated_at` 通用字段。

---

## 二、基础设施层 (Infrastructure Layer)

### 2.1 LLM Provider 适配器

```
backend/app/providers/
├── base.py           # BaseLLMProvider (ABC)
├── openai_compat.py  # OpenAI 兼容实现
├── reranker.py       # Jina Reranker 适配器
└── registry.py       # Provider 注册与路由
```

#### BaseLLMProvider 接口

```python
class BaseLLMProvider(ABC):
    async def chat(messages, model, temperature, max_tokens) -> ChatResponse
    async def chat_stream(messages, model, temperature, max_tokens) -> AsyncIterator[ChatChunk]
    async def structured_output(messages, model, output_schema: Type[BaseModel]) -> BaseModel
    async def embedding(texts: list[str], model) -> list[list[float]]
    def count_tokens(text, model) -> int
```

#### Provider 配置

- 数据库存储 `provider_configs` 表
- 支持多实例（不同中转地址/模型）
- 每个 Agent 可独立配置 Provider + 模型
- API Key 使用 Fernet 对称加密存储
- Fallback 链：主 Provider 失败 → 备用 Provider

#### 重试策略

- 指数退避，最多3次
- 429 (Rate Limit) → 延长间隔重试
- 500 (Server Error) → 立即重试
- 超时 120s → 切换 fallback Provider

### 2.2 任务队列 (Celery + Redis)

```
backend/app/jobs/
├── celery_app.py  # Celery 应用配置
├── writing.py     # 写作任务 (writing 队列)
├── audit.py       # 审计任务 (audit 队列)
└── settler.py     # 结算任务 (default 队列)
```

- 三队列：`default` / `writing` / `audit`
- Worker 并发数：4
- 支持任务优先级、超时、重试

### 2.3 事件总线

基于 Redis Pub/Sub：
- Agent 执行进度 → 前端 SSE 推送
- 真相文件更新 → 缓存失效
- 审计完成 → 触发后续流程

### 2.4 结构化日志

structlog 全链路追踪：`request_id → job_id → agent_id → llm_call_id`

---

## 三、领域引擎层 (Domain Engines)

### 3.1 世界模型引擎

```python
# backend/app/engines/world_model.py
class WorldModelEngine:
    # 实体管理
    async def create_entity(project_id, entity_data) -> Entity
    async def update_entity(entity_id, updates) -> Entity
    async def lock_attributes(entity_id, attributes) -> Entity

    # 实体自动提取 (NER + Aho-Corasick + jieba)
    async def extract_entities(text, project_id) -> list[ExtractedEntity]
    # 置信度分级：>0.8 自动入库 / 0.5~0.8 warning / <0.5 忽略

    # 实时上下文匹配
    def build_automaton(project_id) -> ahocorasick.Automaton
    def match_entities(text, automaton) -> list[Entity]

    # POV-aware 过滤
    async def filter_context_for_pov(pov_character_id, context) -> FilteredContext
```

依赖：`pyahocorasick`, `jieba`

### 3.2 混合 RAG 引擎

```python
# backend/app/engines/hybrid_rag.py
class HybridRAGEngine:
    # 三通道并行检索
    async def vector_search(query_embedding, top_k) -> list[SearchResult]    # pgvector
    async def bm25_search(query_text, top_k) -> list[SearchResult]           # rank_bm25
    async def graph_search(entity_id, depth) -> list[SearchResult]           # 图谱 N 度

    # 融合与精排
    async def rrf_fusion(results_channels, k=60) -> list[SearchResult]
    async def rerank(candidates, query, top_m) -> list[SearchResult]         # Jina API

    # 完整检索流程
    async def retrieve(query, project_id, pov_character_id, top_m) -> list[SearchResult]
```

上下文预算分配 (200K token 模型)：
- System Prompt + Rules: ~3K
- 世界设定摘要: ~5K
- POV 角色状态: ~3K
- 前文摘要(最近5章): ~8K
- 当前章已写内容: ~10K
- RAG 检索结果: ~5K
- 场景卡+章节目标: ~2K
- 节奏建议: ~1K
- 输出预留: ~6K

渐进式上下文策略：
- 第1-5章：注入完整设定 + 全部前文
- 第6-20章：设定摘要 + 最近3章全文 + 更早章节摘要
- 第21章+：设定摘要 + 最近2章全文 + RAG 检索片段 + 真相文件快照

### 3.3 质量审计系统

```python
# backend/app/engines/quality_audit.py
class AuditRunner:
    async def audit_chapter(chapter_id, mode="full") -> AuditReport
    # mode: "full" (33维度) / "incremental" (修改相关) / "quick" (确定性检查)
```

六大类 33 维度：

| 类别 | 维度数 | 维度列表 |
|------|--------|----------|
| 一致性 | 8 | 角色设定冲突、角色记忆违反、世界观违反、时间线矛盾、物资连续性、地理矛盾、锁定属性违反、前后文逻辑矛盾 |
| 叙事质量 | 7 | 大纲遵守度、场景目标完成度、章节钩子有效性、信息密度、节奏感、悬念维持、对话/叙述比例 |
| 角色 | 6 | OOC检测、角色弧线推进、关系演变合理性、对话风格一致性、情感弧线连贯性、角色能力边界 |
| 结构 | 4 | 伏笔埋设与回收、支线进度、全书节奏曲线、章节内三幕结构 |
| 风格 | 4 | AI痕迹检测、重复表达检测、禁用词句检测、风格一致性 |
| 爽点 | 4 | 爽点密度、爽点模式识别、高潮对齐大纲、读者钩子有效性 |

评分体系：
- 每维度 0-10 分
- 严重度分级：pass(≥7) / warning(4-6) / error(1-3) / blocking(0)
- 存在 blocking → 必须修订
- 总分 ≥ 28/33 → 非阻塞，可选修订
- 总分 < 20/33 → 需要 rework 级重写

确定性检查（零 LLM 成本）：物资连续性(#5)、锁定属性违反(#7)、AI痕迹(#26)、重复表达(#27)、禁用词句(#28)

### 3.4 状态管理器 (10 个真相文件)

```python
# backend/app/engines/state_manager.py
class StateManager:
    async def get_truth_file(project_id, file_type) -> TruthFile
    async def update_truth_file(project_id, file_type, diff, chapter_id) -> TruthFile
    # 原子更新 + 版本号递增 + 历史记录入 truth_file_history
    async def get_truth_file_at_version(truth_file_id, version) -> TruthFileHistory
```

10 个真相文件类型：

| 文件 | 职责 | 更新频率 |
|------|------|----------|
| story_bible | 不可变核心设定 | 极少修改 |
| volume_outline | 分卷结构 | 每卷开始时 |
| book_rules | 三层规则 | 初始化时 |
| current_state | 全局状态快照 | 每章写完 |
| particle_ledger | 物资追踪 | 每章写完 |
| pending_hooks | 未回收伏笔 | 每章写完 |
| chapter_summaries | 章节摘要 | 每章写完 |
| subplot_board | 支线看板 | 每章写完 |
| emotional_arcs | 情感弧线 | 每章写完 |
| character_matrix | 角色交互矩阵 | 每章写完 |

更新协议：Writer Phase2 输出 → Observer 提取事实 → Settler 计算 diff → 原子更新 → 版本递增 → 历史入库

### 3.5 节奏控制器 (Strand Weave)

```python
# backend/app/engines/pacing_control.py
class PacingController:
    def analyze_pacing(project_id) -> PacingAnalysis
    def suggest_next_chapter(project_id) -> PacingSuggestion
    def check_red_lines(project_id) -> list[RedLineViolation]
```

三线交织：Quest(60%) / Fire(20%) / Constellation(20%)

红线规则：
- Quest 连续不超过 5 章
- Fire 断档不超过 3 章
- 情感弧线连续 4 章低迷 → 触发转折
- 每章至少包含 2 种 Strand

爽点基准：
- 每章 ≥ 1 个 cool-point
- 每 5 章 ≥ 1 个 combo
- 每 10 章 ≥ 1 个 milestone victory

6 种爽点模式：装逼打脸 / 扮猪吃虎 / 越级反杀 / 打脸权威 / 反派翻车 / 甜蜜超预期

### 3.6 去 AI 味引擎

```python
# backend/app/engines/de_ai.py
class DeAIEngine:
    def detect(text) -> list[AITrace]      # 200+ 疲劳词表 + 禁用句式正则
    def get_fatigue_words() -> list[str]   # 疲劳词表
    def get_banned_patterns() -> list[re.Pattern]  # 禁用句式
    def track_stats(project_id, chapter_id, traces) -> None  # 统计追踪
```

四层处理：
1. **预防** (Writer Prompt)：嵌入疲劳词禁用表 + 禁用句式 + 正面引导
2. **检测** (Auditor #26)：AIDetector 扫描
3. **修订** (Reviser anti-detect)：替换疲劳词 + 重写句式 + 匹配角色指纹
4. **统计** (全局)：追踪密度趋势 + 持续优化禁用表

### 3.7 上下文过滤器

```python
# backend/app/engines/context_filter.py
class ContextFilter:
    async def assemble_context(chapter_id, pov_character_id) -> AssembledContext
    # POV-aware：仅注入该角色亲历/被告知的事件
    # 参考 character_matrix 的知识边界
    # 隐藏其他角色内心独白和秘密
```

---

## 四、编排层 (Orchestration Layer)

### 4.1 Agent 基类

```python
# backend/app/agents/base.py
class BaseAgent(ABC):
    name: str
    description: str
    system_prompt_template: str
    input_schema: Type[BaseModel]
    output_schema: Type[BaseModel]
    temperature: float
    max_retries: int = 3
    timeout_seconds: int = 120

    async def execute(self, context: AgentContext) -> AgentResult
    async def build_messages(self, context: AgentContext) -> list[Message]
    async def validate_output(self, result: AgentResult) -> list[ValidationIssue]
    async def on_retry(self, error: Exception, attempt: int) -> None
```

### 4.2 七 Agent 管线

| Agent | 温度 | 职责 | LLM |
|-------|------|------|-----|
| Radar | 0.3 | 分析状态，确定下一步任务 | 通用模型 |
| Architect | 0.4 | 结构规划(主线/分卷/章节/场景卡) | 通用模型 |
| Context Agent | — | 非LLM：RAG检索 + POV过滤 + 节奏注入 | 纯工程逻辑 |
| Writer (Phase1) | 0.7 | 创意写作 | 写作模型 |
| Writer (Phase2) | 0.3 | 状态结算 | 同上 |
| Settler | 0.2 | Observer(事实提取) + Settler(真相文件更新) + 实体入库 | 快速模型 |
| Auditor | 0.2 | 33维度质量审计 | 稳定模型 |
| Reviser | 0.5 | 五模式修订(polish/rewrite/rework/spot-fix/anti-detect) | 写作模型 |

```
backend/app/agents/
├── base.py
├── radar.py
├── architect.py
├── context_agent.py
├── writer.py
├── settler.py
├── auditor.py
└── reviser.py
```

### 4.3 Pipeline DAG 执行器

```
backend/app/orchestration/
├── pipeline.py       # DAG 执行引擎
├── state_machine.py  # 工作流状态机
├── scheduler.py      # 任务调度器
└── human_loop.py     # 人机协作中断点
```

DAG 能力：
- 拓扑排序：同层 Agent 并行执行
- 条件分支：审计通过/不通过走不同路径
- 循环：Auditor↔Reviser (最多3轮)
- 人机中断点：always / on_low_score / on_first_run / never
- 断点恢复：每个节点结果持久化，崩溃后从最后完成节点恢复
- 超时降级：单 Agent 超时自动切换 fallback Provider

全自动写一章的 DAG：

```
radar → architect(chapter_brief)
  → [并行] context_agent + pacing_controller.suggest()
    → writer_phase1 (创意写作)
      → writer_phase2 (状态结算)
        → settler (更新真相文件 + 实体入库)
          → auditor (33维度审计)
            → [条件分支]
              ├─ [通过] → de_ai_engine → 完成
              └─ [不通过] → reviser → auditor（最多3轮）
                            └─ [3轮仍不通过] → 标记人工干预
```

### 4.4 五阶段工作流

| 阶段 | 名称 | 执行者 | 输出 | 人机 |
|------|------|--------|------|------|
| 1 | 项目初始化 | Architect | story_bible + book_rules | 必须人工确认 |
| 2 | 主线规划 | Architect | plot_blueprint + volume_outline | 候选稿选择 |
| 3 | 分卷分章 | Architect | chapters + scene_cards | 可调整 |
| 4 | 逐章生成 | 全管线DAG | final_draft per chapter | 按模式 |
| 5 | 卷末检查 | Auditor(卷级) | 卷级报告 | 决定后续调整 |

两种运行模式：
- **全自动**：DAG 自动流转，仅严重问题暂停
- **半自动**：每个 Agent 输出后等待人工审阅

人机中断点配置：
```python
class HumanLoopPoint:
    trigger: str       # "always" | "on_low_score" | "on_first_run" | "never"
    timeout_hours: float
    fallback: str      # "auto_accept" | "auto_reject" | "pause"
```

### 4.5 防幻觉三定律

1. **大纲即法律**：Writer 输出必须严格对应 volume_outline
2. **设定即物理**：世界观规则不可被 AI 修改，违反即 blocking
3. **发明需识别**：新实体必须经 Settler 识别入库

### 4.6 三层规则体系

- **第一层 — 基础护栏** (~25条)：性格一致、对话个性、show don't tell、冲突驱动、感官细节、因果完整、伏笔有埋有收、禁用疲劳词
- **第二层 — 题材特性** (Genre Profile)：预置模板(玄幻/仙侠/都市/恐怖/科幻/言情/自定义)，含特有禁忌、审计维度开关、数值体系开关
- **第三层 — 本书规则** (Book Rules)：项目个性化规则(主角性格锁定、行为约束、禁忌、数值硬上限、资源类型、自定义审计维度)

---

## 五、网关层 (API Gateway)

### 5.1 FastAPI 应用结构

```
backend/app/api/
├── projects.py      # 项目 CRUD
├── volumes.py       # 分卷管理
├── chapters.py      # 章节 CRUD + 状态管理
├── worldmodel.py    # 世界模型 CRUD + 图谱查询
├── agents.py        # Agent 管线控制 (启动/暂停/恢复/取消)
├── audit.py         # 质量审计接口
├── hooks.py         # 伏笔管理
├── ws.py            # WebSocket 实时推送
└── auth.py          # Token 认证
```

### 5.2 认证

极简 Token 认证：
- 环境变量 `AUTH_TOKEN` 配置固定 token
- 请求头 `Authorization: Bearer <token>` 验证
- 无 OAuth / 无多租户 / 无用户管理

### 5.3 实时通信

- **WebSocket**：Agent 执行进度实时推送
- **SSE**：备选方案
- 消息类型：`agent_start` / `agent_progress` / `agent_complete` / `agent_error` / `human_loop_request`

### 5.4 安全与限流

- CORS 白名单
- Pydantic v2 严格模式输入校验
- Prompt 注入防护（用户输入清洗）
- LLM 调用速率限制
- 全链路审计日志 (request_id 追踪)

### 5.5 API 设计原则

- RESTful CRUD + 少量 RPC 端点 (如 `POST /agents/run-chapter`)
- OpenAPI 文档自动生成
- 统一错误响应格式：`{ "error": { "code": str, "message": str, "details": any } }`
- 分页：`?page=1&page_size=20`
- 排序：`?sort_by=created_at&sort_order=desc`

---

## 六、表现层 (Presentation Layer)

### 6.1 技术栈

- **框架**：Next.js 15 App Router + React 19
- **UI库**：Tailwind CSS + shadcn/ui
- **图谱可视化**：ReactFlow
- **状态管理**：React Query (服务端) + Zustand (客户端)
- **编辑器**：TipTap 或 Lexical (富文本)

### 6.2 Studio (创作现场)

- 章节列表（树形：卷→章→场景卡）
- 富文本编辑器（查看/编辑草稿）
- Agent 执行面板（实时进度、日志流）
- 人机协作界面（候选稿对比、审批）
- 真相文件查看器

### 6.3 Atlas (世界图谱)

- ReactFlow 实体关系可视化
- 实体详情面板（属性、别名、知识边界）
- 时间轴过滤（按章节过滤关系状态）
- 冲突检测高亮（设定矛盾标红）
- 实体 CRUD

### 6.4 Dashboard (运维面板)

- 审计报告（33维度雷达图）
- 节奏仪表盘（Strand Weave 曲线）
- 伏笔追踪看板
- LLM 成本统计
- 系统健康状态

### 6.5 实时通信

- WebSocket 连接管理 + 心跳
- Agent 进度实时渲染
- 人机协作请求弹窗

---

## 七、部署架构

### 7.1 Docker Compose

```
services:
  postgres:     pgvector/pgvector:pg17    :5432
  redis:        redis:8-alpine            :6379
  backend:      ./backend (FastAPI)       :8000
  celery-worker: ./backend (4 concurrency, 3 queues: default/writing/audit)
  celery-beat:  ./backend (scheduler)
  flower:       mher/flower               :5555
  frontend:     ./frontend (Next.js)      :3000
```

### 7.2 监控 (Prometheus + Grafana)

- LLM 指标：调用量 / token消耗 / 延迟 / 错误率
- 管线指标：Agent耗时 / 审计通过率 / 修订轮次 / 去AI味通过率
- 系统指标：CPU/内存/磁盘 / 队列长度 / 连接池
- 业务指标：日生成章节数 / 采纳率 / 人工干预率 / 伏笔回收率

告警规则：单次调用>60s / 错误率>5% / 单日成本超预算 / 审计通过率<80%

---

## 八、迭代实施路线图

### 迭代 1：项目骨架 + 数据层 (2-3周)

- 初始化项目结构 (FastAPI backend + Next.js frontend)
- Docker Compose 配置 (pgvector/pg17 + Redis 8)
- 数据库 Schema (全部表) + Alembic 迁移
- 基础 CRUD API (projects, volumes, chapters, entities)
- LLM Provider 适配器基类 + OpenAI 兼容实现
- 极简 Token 认证

### 迭代 2：核心 Agent 管线 (3-4周)

- BaseAgent 基类
- 7 个 Agent 实现
- Pipeline DAG 执行器 (拓扑排序/条件分支/循环)
- Celery 任务队列集成
- 世界模型引擎基础版 (jieba + pyahocorasick)
- POV-aware 上下文过滤

### 迭代 3：质量保障 + 网文特化 (3-4周)

- 三层规则体系 + 题材 Profile (玄幻/仙侠/都市)
- 黄金三章规则
- Auditor Agent + 33 维度审计
- Reviser Agent 五模式修订
- De-AI Engine 四层去 AI 味
- Pacing Controller (Strand Weave + 爽点密度)

### 迭代 4：RAG + 前端 (3-4周)

- Hybrid RAG (pgvector + BM25 + 图谱 + RRF + Jina Reranker)
- Studio 页面 (创作现场)
- Atlas 页面 (世界图谱 ReactFlow)
- Dashboard 页面 (审计/节奏/伏笔/成本)
- WebSocket/SSE 实时推送

### 迭代 5：生产化加固 (2周)

- Provider fallback
- 管线断点恢复
- E2E 测试
- 半自动模式 (人机协作中断点)
- 结构化日志 (structlog)
- 用量统计与成本追踪
- 数据导出 (txt/epub/markdown)

---

## 九、非功能性需求

### 性能指标

| 指标 | 目标 |
|------|------|
| 单章生成端到端 | < 5 分钟 |
| 大纲生成(单节点) | < 30 秒 |
| API CRUD (P99) | < 200ms |
| 混合 RAG 检索 | < 500ms |
| 并发 Agent 执行数 | ≥ 4 |
| 前端首屏加载 | < 2s |

### 安全性

- API 密钥 Fernet 对称加密存储
- Pydantic v2 严格模式校验
- Prompt 注入防护
- LLM 输出安全检查
- CORS 白名单
- LLM 速率限制

### 可靠性

- LLM 指数退避重试 (max 3)
- Provider fallback
- 管线断点恢复
- 候选稿不覆盖正式稿
- PostgreSQL pg_dump + WAL 归档
- RAG 不可用时回退简单上下文
