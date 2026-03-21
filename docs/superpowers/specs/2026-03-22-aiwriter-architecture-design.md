# AiWriter — AI 自动写小说系统概要设计文档

> 基于 production.md 架构设计文档，严格跟随其定义的六层架构、七Agent管线、核心引擎体系。

## 技术决策摘要

| 决策点 | 选择 | 理由 |
|--------|------|------|
| LLM Provider | OpenAI 兼容中转 API | 统一接口，灵活切换后端模型。放弃原生 Claude/Gemini 适配器，因中转 API 已覆盖所有模型调用场景；如需原生特性（如 Claude 工具调用），可在迭代5扩展 |
| Embedding | text-embedding-3-large (1536维, API) | 部署简单，无需本地 GPU。放弃 BGE-M3 (1024维) 的理由：与中转 API 策略一致，减少本地推理依赖。向量维度通过配置参数化 (`EMBEDDING_DIM=1536`)，便于未来切换 |
| Reranker | Jina Reranker v3 (API) | 与整体 API 调用策略一致，放弃本地 BGE-Reranker-v2 |
| 对象存储 | 暂用本地文件系统 | 个人自用场景下暂不引入 MinIO，本地 `./storage/` 目录存储导出文件(epub/txt/markdown)，Docker volume 挂载持久化。迭代5可评估是否引入 MinIO |
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

### 1.3 本地文件存储

- 目录：`./storage/` (Docker volume 挂载)
- 用途：导出文件 (epub/txt/markdown)、临时文件
- 未来可评估引入 MinIO 替代

### 1.4 核心表设计

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
| scene_cards | 场景卡 | chapter_id, pov_character_id, location, time_marker, goal, conflict, outcome, characters(JSONB), notes, sort_order |
| hooks | 伏笔 | hook_type(foreshadow/cliffhanger/chekhov_gun), planted_chapter_id, expected_resolve_chapter, status(open/resolved/abandoned) |
| pacing_meta | 节奏元数据 | chapter_id(UNIQUE), quest_ratio, fire_ratio, constellation_ratio, highlight_count, highlight_types(JSONB), tension_level, strand_tags(JSONB) |
| audit_records | 审计记录 | chapter_id, draft_id, dimension, category(consistency/narrative/character/structure/style/engagement), score(0-10), severity(pass/warning/error/blocking), evidence(JSONB) |
| memory_entries | 章节记忆 | chapter_id, summary, embedding(vector 1536) |
| worldbook | 世界书条目 | 自由格式设定条目 |
| style_presets | 风格预设 | 写作风格模板 |
| book_rules | 本书规则 | 三层规则体系 |
| outline_candidates | 大纲候选稿 | project_id, stage(plot_blueprint/volume_outline/chapter_plan), content(JSONB), selected(bool) |

#### 全局表

| 表名 | 职责 |
|------|------|
| provider_configs | 模型提供商配置 (API地址/密钥/模型名/参数) |
| usage_records | 用量追踪 (模型/token消耗/成本/时间) |
| job_runs | 任务执行记录 (Agent链路/状态/耗时) |
| workflow_presets | 工作流模板 |

### 1.6 Python 模型组织

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
├── outline_candidate.py
├── provider_config.py
├── usage_record.py
├── job_run.py
└── workflow_preset.py
```

统一使用 SQLAlchemy 2.0 声明式映射 (DeclarativeBase)，所有模型包含 `id (UUID)`, `created_at`, `updated_at` 通用字段。

### 1.7 数据库连接管理

```
backend/app/db/
├── session.py       # AsyncSession 工厂 + 连接池配置
├── base.py          # DeclarativeBase + 通用 Mixin
└── migrations/      # Alembic 迁移目录
```

连接池配置：
- `pool_size`: 10 (默认)
- `max_overflow`: 20
- `pool_timeout`: 30s
- `pool_recycle`: 3600s (1小时回收)
- 会话生命周期：请求级别 (FastAPI 依赖注入)

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

### 2.4 混合 RAG 引擎 (Hybrid RAG Engine)

> 注：遵循 production.md 1.1 节，RAG 引擎归入基础设施层。领域引擎层调用 RAG 进行检索。

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

### 2.5 结构化日志

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

### 3.2 质量审计系统

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
- 通过率 (score≥7的维度数 / 启用维度数) ≥ 85% → 非阻塞，可选修订
- 通过率 < 60% → 需要 rework 级重写
- 注：题材 Profile 可禁用部分维度，分母随之变化

确定性检查（零 LLM 成本）：物资连续性(#5)、锁定属性违反(#7)、AI痕迹(#26)、重复表达(#27)、禁用词句(#28)

### 3.3 状态管理器 (10 个真相文件)

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

### 3.4 节奏控制器 (Strand Weave)

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

### 3.5 去 AI 味引擎

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

### 3.6 上下文过滤器

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

| Agent | 温度 | 职责 | 推荐模型 (通过中转API调用) |
|-------|------|------|---------------------------|
| Radar | 0.3 | 分析状态，确定下一步任务 | GPT-4o / Claude Haiku |
| Architect | 0.4 | 结构规划(主线/分卷/章节/场景卡) | Claude Sonnet / GPT-4o |
| Context Agent | — | 非LLM：RAG检索 + POV过滤 + 节奏注入 | 纯工程逻辑(无需LLM) |
| Writer (Phase1) | 0.7 | 创意写作 | Claude Sonnet (写作质量最佳) |
| Writer (Phase2) | 0.3 | 状态结算 | 同上 |
| Settler | 0.2 | Observer(事实提取) + Settler(真相文件更新) + 实体入库 | Gemini Flash (快速低成本) |
| Auditor | 0.2 | 33维度质量审计 | GPT-4o (结构化输出稳定) |
| Reviser | 0.5 | 五模式修订(polish/rewrite/rework/spot-fix/anti-detect) | Claude Sonnet |

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

### 4.2.1 Writer Agent Prompt 结构模板

```
[SYSTEM]
你是一位专注于{genre}的小说作家。

## 写作风格
{style_preset_content}

## 规则（必须严格遵守）

### 基础护栏
{base_guardrails_25_rules}

### 题材规则
{genre_profile_content}

### 本书规则
{book_rules_yaml}

## 禁止
- 不使用以下词语：{fatigue_words_top_100}
- 不使用以下句式：{banned_patterns_top_30}

## 要求
- 每个场景必须推进至少一个冲突
- 对话必须体现角色个性差异
- 描写必须包含至少两种感官细节
- 展示而非告知

[USER]
## 当前章节目标
{chapter_brief}

## 场景卡
{scene_card_content}

## POV 角色当前状态
{pov_character_state_from_current_state}

## 前文摘要（仅 POV 角色所知）
{pov_filtered_chapter_summaries}

## 相关设定（自动检索）
{rag_retrieved_worldbook_entries}

## 角色对话指纹
{dialogue_fingerprints_for_appearing_characters}

## 节奏建议
{pacing_suggestion}

## 任务
请基于以上信息写出本场景的正文。字数目标：{target_words}字。
直接输出小说正文，不要任何元数据或标注。
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

### 4.7 黄金三章规则 (网文核心差异化)

内置到 Architect Agent 的 Prompt 中：

| 章节 | 规则 | 目的 |
|------|------|------|
| 第1章 | 抛出核心冲突，禁止大段背景灌输 | 快速抓住读者注意力 |
| 第2章 | 展示金手指/核心能力，让读者看到爽点预期 | 建立阅读期待 |
| 第3章 | 明确短期目标，给读者追读理由 | 留住读者 |

Architect 在规划前3章时，强制执行黄金三章约束：
- 第1章 scene_card 必须包含 `conflict: "核心冲突"` 标记
- 第2章 scene_card 必须包含 `highlight_type: "金手指展示"` 标记
- 第3章 scene_card 必须包含 `goal: "短期目标明确"` 标记
- Auditor 在审计前3章时，额外检查黄金三章规则的遵守度

---

## 四点五、业务服务层 (Services Layer)

封装跨模型/跨引擎的业务逻辑，API 层调用 Service，Service 调用 Engine/Model。

```
backend/app/services/
├── project_service.py    # 项目创建(含初始化10个真相文件)、项目设置
├── chapter_service.py    # 章节生命周期管理
├── entity_service.py     # 实体 CRUD + 自动提取 + 图谱查询
├── truth_file_service.py # 真相文件读写 + 版本管理
├── pipeline_service.py   # 管线触发 + 状态查询 + 中断处理
├── export_service.py     # 数据导出 (txt/epub/markdown)
└── usage_service.py      # 用量统计与成本查询
```

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

### 5.6 核心 API 端点清单

#### 项目管理

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/projects` | 项目列表 |
| POST | `/api/projects` | 创建项目 (含初始化10个真相文件) |
| GET | `/api/projects/{id}` | 项目详情 |
| PUT | `/api/projects/{id}` | 更新项目 |
| DELETE | `/api/projects/{id}` | 删除项目 |

#### 分卷/章节

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/projects/{id}/volumes` | 分卷列表 |
| POST | `/api/projects/{id}/volumes` | 创建分卷 |
| GET | `/api/projects/{id}/chapters` | 章节列表 (支持 volume_id 过滤) |
| POST | `/api/projects/{id}/chapters` | 创建章节 |
| GET | `/api/chapters/{id}` | 章节详情 (含 drafts/scene_cards) |
| PUT | `/api/chapters/{id}` | 更新章节 |

#### 世界模型

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/projects/{id}/entities` | 实体列表 (支持 type 过滤) |
| POST | `/api/projects/{id}/entities` | 创建实体 |
| PUT | `/api/entities/{id}` | 更新实体 |
| GET | `/api/projects/{id}/relationships` | 关系列表 |
| POST | `/api/projects/{id}/relationships` | 创建关系 |
| GET | `/api/projects/{id}/graph` | 图谱查询 (N度路径) |

#### Agent 管线控制

| Method | Path | 说明 | 关键参数 |
|--------|------|------|----------|
| POST | `/api/projects/{id}/pipeline/init` | 触发项目初始化 (阶段1) | `{genre, style, target_words, core_idea}` |
| POST | `/api/projects/{id}/pipeline/plan` | 触发主线规划 (阶段2) | `{candidate_count: int}` |
| POST | `/api/projects/{id}/pipeline/outline` | 触发分卷分章 (阶段3) | `{volume_id}` |
| POST | `/api/projects/{id}/pipeline/write-chapter` | 触发逐章生成 (阶段4) | `{chapter_id, mode: "auto"|"semi"}` |
| POST | `/api/projects/{id}/pipeline/volume-check` | 触发卷末检查 (阶段5) | `{volume_id}` |
| GET | `/api/pipeline/jobs/{job_id}` | 查询任务状态 | — |
| POST | `/api/pipeline/jobs/{job_id}/pause` | 暂停任务 | — |
| POST | `/api/pipeline/jobs/{job_id}/resume` | 恢复任务 | — |
| POST | `/api/pipeline/jobs/{job_id}/cancel` | 取消任务 | — |
| POST | `/api/pipeline/human-loop/{id}/approve` | 人工审批 | `{action: "approve"|"reject"|"edit", content?}` |

#### 审计/伏笔/真相文件

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/chapters/{id}/audit` | 获取章节审计报告 |
| POST | `/api/chapters/{id}/audit` | 触发章节审计 (mode: full/incremental/quick) |
| GET | `/api/projects/{id}/hooks` | 伏笔列表 |
| GET | `/api/projects/{id}/truth-files` | 真相文件列表 |
| GET | `/api/projects/{id}/truth-files/{type}` | 获取指定真相文件 |
| GET | `/api/projects/{id}/truth-files/{type}/history` | 真相文件历史 |

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

## 九、扩展策略

### 水平扩展

- Celery worker 按队列拆分 (writing / audit / settler 各自独立伸缩)
- PostgreSQL read replica 分离读写

### 功能扩展点 (插件化设计)

| 扩展类型 | 方式 |
|----------|------|
| 新模型 | 在 `providers/` 添加适配器 + 在 ProviderType 枚举注册 |
| 新 Agent | 在 `agents/` 添加 Agent 类 + 在 Pipeline DAG 配置中注册 |
| 新题材 | 在 genre_profiles 目录添加 YAML 模板 |
| 新审计维度 | 在审计维度注册表添加 Check 类 |

---

## 十、非功能性需求

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
