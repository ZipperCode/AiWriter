╭────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ Plan to implement                                                                                                  │
│                                                                                                                    │
│ AI 自动写小说系统 — 生产级架构设计文档                                                                             │
│                                                                                                                    │
│ Context                                                                                                            │
│                                                                                                                    │
│ 主人希望开发一款生产级 AI 自动写小说工具。浮浮酱调研了四个开源项目（NovelWriter、InkOS、Webnovel                   │
│ Writer、MuMuAINovel），提炼各自精华，结合业界最新技术方案，综合设计出一份可直接落地实施的完整架构文档喵～          │
│                                                                                                                    │
│ 项目定位： 全新项目，个人/小团队自用，以网文创作为主要场景。                                                       │
│                                                                                                                    │
│ 核心设计理念： 取四个项目之长，融合为最优方案：                                                                    │
│ - NovelWriter → 动态世界模型（实体-关系-体系图）+ 实时上下文过滤                                                   │
│ - InkOS → 五 Agent 管线 + 7 真相文件 + 33 维度审计 + 去 AI 味体系                                                  │
│ - Webnovel Writer → 混合 RAG + Strand Weave 节奏系统 + 爽点密度基准 + 防幻觉三定律                                 │
│ - MuMuAINovel → 全栈 Web UI + 多模型支持 + Docker 部署                                                             │
│                                                                                                                    │
│ 简化决策（个人自用）：                                                                                             │
│ - 认证层采用极简方案（单用户密码或环境变量 token），不做 OAuth/多租户                                              │
│ - 不需要计费系统，但保留 LLM 用量追踪（成本感知）                                                                  │
│ - 部署以 Docker Compose 为终态，不需要 K8s                                                                         │
│                                                                                                                    │
│ ---                                                                                                                │
│ 一、系统总体架构                                                                                                   │
│                                                                                                                    │
│ 1.1 六层架构                                                                                                       │
│                                                                                                                    │
│ ┌─────────────────────────────────────────────────────────────────┐                                                │
│ │                     表现层 (Presentation)                        │                                               │
│ │  Next.js 15 App Router / React 19                               │                                                │
│ │  Studio (创作现场) + Atlas (世界图谱) + Dashboard (运维面板)      │                                              │
│ ├─────────────────────────────────────────────────────────────────┤                                                │
│ │                     网关层 (API Gateway)                         │                                               │
│ │  FastAPI + WebSocket / SSE                                      │                                                │
│ │  简易 Token 认证 / 限流 / 请求追踪                               │                                               │
│ ├─────────────────────────────────────────────────────────────────┤                                                │
│ │                     编排层 (Orchestration)                       │                                               │
│ │  Agent Pipeline Engine (DAG) / Workflow State Machine            │                                               │
│ │  人机协作中断点 / 任务调度                                       │                                               │
│ ├─────────────────────────────────────────────────────────────────┤                                                │
│ │                     领域引擎层 (Domain Engines)                   │                                              │
│ │  World Model Engine / Quality Audit System (33维)               │                                                │
│ │  Pacing Control (Strand Weave) / De-AI Engine / Context Filter  │                                                │
│ ├─────────────────────────────────────────────────────────────────┤                                                │
│ │                     基础设施层 (Infrastructure)                   │                                              │
│ │  LLM Provider Adapters / Hybrid RAG Engine (向量+BM25+图谱)     │                                                │
│ │  Task Queue (Celery+Redis) / Event Bus                          │                                                │
│ ├─────────────────────────────────────────────────────────────────┤                                                │
│ │                     持久化层 (Persistence)                       │                                               │
│ │  PostgreSQL 17 + pgvector / Redis 8 / Object Storage (MinIO)    │                                                │
│ └─────────────────────────────────────────────────────────────────┘                                                │
│                                                                                                                    │
│ 1.2 技术栈选型                                                                                                     │
│                                                                                                                    │
│ ┌────────────┬────────────────────────────────────┬─────────────────────────────────────────────────┐              │
│ │    组件    │                选型                │                      理由                       │              │
│ ├────────────┼────────────────────────────────────┼─────────────────────────────────────────────────┤              │
│ │ 后端框架   │ FastAPI                            │ async 原生、Pydantic 校验、OpenAPI 文档自动生成 │              │
│ ├────────────┼────────────────────────────────────┼─────────────────────────────────────────────────┤              │
│ │ 前端框架   │ Next.js 15 + React 19              │ SSR/SSG、App Router、Server Components          │              │
│ ├────────────┼────────────────────────────────────┼─────────────────────────────────────────────────┤              │
│ │ 结构化存储 │ PostgreSQL 17 + pgvector           │ JSONB 支持真相文件、pgvector 内置向量检索       │              │
│ ├────────────┼────────────────────────────────────┼─────────────────────────────────────────────────┤              │
│ │ 缓存/队列  │ Redis 8                            │ 任务 Broker、会话缓存、SSE 消息总线             │              │
│ ├────────────┼────────────────────────────────────┼─────────────────────────────────────────────────┤              │
│ │ 任务执行   │ Celery                             │ 分布式任务队列、重试/超时/监控、可水平扩缩      │              │
│ ├────────────┼────────────────────────────────────┼─────────────────────────────────────────────────┤              │
│ │ 中文分词   │ jieba                              │ 世界模型上下文匹配、实体别名扩展                │              │
│ ├────────────┼────────────────────────────────────┼─────────────────────────────────────────────────┤              │
│ │ 多模式匹配 │ pyahocorasick                      │ Aho-Corasick 自动机，O(n) 并行实体匹配          │              │
│ ├────────────┼────────────────────────────────────┼─────────────────────────────────────────────────┤              │
│ │ 全文检索   │ rank_bm25                          │ 混合 RAG 的关键词检索通道                       │              │
│ ├────────────┼────────────────────────────────────┼─────────────────────────────────────────────────┤              │
│ │ Reranker   │ BGE-Reranker-v2 / Jina Reranker v3 │ RRF 融合后的精排                                │              │
│ ├────────────┼────────────────────────────────────┼─────────────────────────────────────────────────┤              │
│ │ Embedding  │ BGE-M3 / text-embedding-3-large    │ 中文语义检索、多语言支持                        │              │
│ ├────────────┼────────────────────────────────────┼─────────────────────────────────────────────────┤              │
│ │ 实时通信   │ WebSocket + SSE                    │ Agent 执行进度实时推送                          │              │
│ ├────────────┼────────────────────────────────────┼─────────────────────────────────────────────────┤              │
│ │ 容器化     │ Docker Compose                     │ 个人自用无需 K8s，Compose 已足够                │              │
│ ├────────────┼────────────────────────────────────┼─────────────────────────────────────────────────┤              │
│ │ 监控       │ Prometheus + Grafana               │ token 消耗、延迟、错误率、业务指标              │              │
│ ├────────────┼────────────────────────────────────┼─────────────────────────────────────────────────┤              │
│ │ 日志       │ structlog                          │ 结构化日志 + 全链路追踪                         │              │
│ └────────────┴────────────────────────────────────┴─────────────────────────────────────────────────┘              │
│                                                                                                                    │
│ 1.3 模块组织结构                                                                                                   │
│                                                                                                                    │
│ backend/app/                                                                                                       │
│ ├── api/                    # HTTP 端点                                                                            │
│ │   ├── projects.py         # 项目 CRUD                                                                            │
│ │   ├── chapters.py         # 章节 CRUD                                                                            │
│ │   ├── volumes.py          # 分卷管理                                                                             │
│ │   ├── worldmodel.py       # 世界模型 CRUD + 图谱查询                                                             │
│ │   ├── agents.py           # Agent 管线控制                                                                       │
│ │   ├── audit.py            # 质量审计接口                                                                         │
│ │   ├── hooks.py            # 伏笔管理                                                                             │
│ │   └── ws.py               # WebSocket 实时推送                                                                   │
│ │                                                                                                                  │
│ ├── models/                 # ORM 模型                                                                             │
│ │   ├── project.py          # 项目                                                                                 │
│ │   ├── volume.py           # 分卷                                                                                 │
│ │   ├── chapter.py          # 章节（含 pov_character_id, timeline_position, status）                               │
│ │   ├── scene_card.py       # 场景卡                                                                               │
│ │   ├── draft.py            # 草稿（含 generation_meta, audit_score）                                              │
│ │   ├── entity.py           # 实体（角色/地点/势力/物品/概念）                                                     │
│ │   ├── relationship.py     # 实体关系                                                                             │
│ │   ├── truth_file.py       # 7+3 真相文件                                                                         │
│ │   ├── book_rules.py       # 本书规则（三层规则体系）                                                             │
│ │   ├── audit_record.py     # 审计记录                                                                             │
│ │   ├── hook.py             # 伏笔/钩子                                                                            │
│ │   ├── pacing_meta.py      # 节奏元数据                                                                           │
│ │   ├── memory_entry.py     # 章节记忆                                                                             │
│ │   ├── worldbook.py        # 世界书条目                                                                           │
│ │   ├── style_preset.py     # 风格预设                                                                             │
│ │   └── provider_config.py  # 模型提供商配置                                                                       │
│ │                                                                                                                  │
│ ├── agents/                 # Agent 定义                                                                           │
│ │   ├── base.py             # Agent 基类：输入/输出/Prompt 模板/重试/日志                                          │
│ │   ├── radar.py            # 侦察 Agent：分析当前状态，确定下一步任务                                             │
│ │   ├── architect.py        # 架构 Agent：结构规划（主线/分卷/章节/场景）                                          │
│ │   ├── context_agent.py    # 上下文 Agent：POV-aware 上下文组装                                                   │
│ │   ├── writer.py           # 写作 Agent：两阶段（创意写作 + 状态结算）                                            │
│ │   ├── settler.py          # 结算 Agent：真相文件原子更新                                                         │
│ │   ├── auditor.py          # 审计 Agent：33 维度质量检查                                                          │
│ │   └── reviser.py          # 修订 Agent：五模式修订                                                               │
│ │                                                                                                                  │
│ ├── engines/                # 领域引擎                                                                             │
│ │   ├── world_model.py      # 世界模型引擎                                                                         │
│ │   ├── hybrid_rag.py       # 混合 RAG 引擎（向量+BM25+图谱+RRF+Rerank）                                           │
│ │   ├── quality_audit.py    # 质量审计系统（33维度）                                                               │
│ │   ├── state_manager.py    # 状态管理（7+3 真相文件）                                                             │
│ │   ├── pacing_control.py   # 节奏控制（Strand Weave）                                                             │
│ │   ├── de_ai.py            # 去 AI 味引擎（四层处理）                                                             │
│ │   └── context_filter.py   # 上下文过滤器（POV-aware）                                                            │
│ │                                                                                                                  │
│ ├── orchestration/          # 编排系统                                                                             │
│ │   ├── pipeline.py         # Agent 管线 DAG 执行器                                                                │
│ │   ├── state_machine.py    # 工作流状态机                                                                         │
│ │   ├── scheduler.py        # 任务调度器                                                                           │
│ │   └── human_loop.py       # 人机协作中断点                                                                       │
│ │                                                                                                                  │
│ ├── providers/              # LLM 适配器                                                                           │
│ │   ├── base.py             # 基类（chat/complete/structured_output/embedding）                                    │
│ │   ├── openai.py           # OpenAI / 兼容接口                                                                    │
│ │   ├── anthropic.py        # Claude                                                                               │
│ │   ├── google.py           # Gemini                                                                               │
│ │   └── reranker.py         # Reranker 适配器                                                                      │
│ │                                                                                                                  │
│ ├── services/               # 业务服务层                                                                           │
│ ├── jobs/                   # Celery 任务定义                                                                      │
│ └── db/                     # 数据库（连接池、迁移）                                                               │
│                                                                                                                    │
│ ---                                                                                                                │
│ 二、核心模块详细设计                                                                                               │
│                                                                                                                    │
│ 2.1 世界模型引擎 (World Model Engine)                                                                              │
│                                                                                                                    │
│ 设计来源： NovelWriter 动态实体图 + InkOS 7 真相文件 + Webnovel 自动实体提取                                       │
│                                                                                                                    │
│ 核心能力：                                                                                                         │
│                                                                                                                    │
│ 2.1.1 实体管理                                                                                                     │
│                                                                                                                    │
│ Entity (实体表)                                                                                                    │
│ ├── id, project_id, name                                                                                           │
│ ├── aliases: JSONB              # 别名列表 ["小明", "明哥", "那个少年"]                                            │
│ ├── entity_type: str            # character / location / faction / item / concept / power_system                   │
│ ├── attributes: JSONB           # 可扩展属性（外貌、性格、能力等）                                                 │
│ ├── locked_attributes: JSONB    # 锁定属性（AI不可推翻，人工设定优先）                                             │
│ ├── embedding: vector(1536)     # 向量索引                                                                         │
│ ├── confidence: float           # 自动提取的置信度                                                                 │
│ ├── source: str                 # manual(人工) / auto_extracted(AI提取)                                            │
│ └── knowledge_boundary: JSONB   # 该实体的知识边界（知道什么、不知道什么）                                         │
│                                                                                                                  │
│ Relationship (关系表)                                                                                              │
│ ├── source_entity_id → target_entity_id                                                                            │
│ ├── relation_type: str          # ally/enemy/parent/lover/mentor/subordinate...                                    │
│ ├── attributes: JSO   # 关系细节                                                                         │
│ ├── valid_from_chapter_id       # 关系生效章节                                                                     │
│ └── valid_to_chapter_id         # 关系失效章节（NULL = 当前有效）                                                  │
│                                                                                                                    │
│ 2.1.2 实体自l Writer）                                                                         │
│                                                                                                                    │
│ Writer Agent 输出后，Settler Agent 自动执行：                                                                      │
│ 1. NER（命名实体识别）提取人名/地名/物品名                                                                         │
│ 2. 与已知实体名库åAho-Corasick + jieba 分词）                                                           │
│ 3. 置信度 > 0.8 → 自动入库                                                                                         │
│ 4. 0.5 ~ 0.8 → 标记 warning，等待人工确认                                                                          │
│ 5. < 0.5 → 忽略                                                                                                    │
│                                                                                                                  │
│ 2.1.3 实时上下文匹配（来自 NovelWriter）                                                                           │
│                                                                                                                    │
│ 使用 pyahocorasick 构建自动机：                                                                                    │
│ - 将所有实体名 +名构建为 Aho-Corasick 自动机                                                                    │
│ - 在待生成章节的前文 + 场景卡中进行 O(n) 并行匹配                                                                  │
│ - 找出"当前场景涉及哪些实体"                                                                                       │
│ - 仅将相关实体的设定注入 LLM 上下文                                                                            │
│                                                                                                                    │
│ 2.1.4 POV-aware 过滤（来自 InkOS）                                                                                 │
│                                                                                                                    │
│ 当前 POV 角色的上下文过滤规则：                                                                                    只注入该角色亲历或被告知的事件                                                                                   │
│ - 参考 character_matrix 真相文件中的"知识边界"                                                                     │
│ - 隐藏其他角色的内心独白和秘密行动                                                                                 │
│ - 确保角色不会"知道他不该知道的事"                                                                                 │
│                                                                                                                    │
│ 2.1.5 图谱可视化（来自 NovelWriter Atlas）                                                                         │
│                                                                                                                    │
│ 前端 Atlas 模块：                                                                                      │
│ - 使用 ReactFlow / D3.js 渲染实体关系图                                                                            │
│ - 支持点击查看详情、拖拽编辑关系                                                                                   │
│ - 支持按时间轴过滤（显示某一章时的关系状态）                                                                       │
│ - 支持冲突检测高亮（设定矛盾的关系标红）                                                                           │
│                                                                                                                    │
│ ---                                                                                                                │
│ 2.2 Agent 编排系统 (Agent Orchestration)                                                                           │
│                                                                                                            │
│ 设计来源： InkOS 五 Agent 管线 + Webnovel 双 Agent 架构                                                            │
│                                                                                                                    │
│ 2.2.1 Agent 基类                                                                                                   │
│                                                                                                          │
│ class BaseAgent(ABC):                                                                                              │
│     name: str                          # Agent 标识                                                                │
│     description: str                   # 职责描述                                                                  │
│     system_prompt_template: str        # 系统 Prompt 模板                                                       
│     input_schema: Type[BaseModel]      # 输入 Pydantic 模型                                                        │
│     output_schema: Type[BaseModel]     # 输出 Pydantic 模型（结构化输出）                                          │
│     temperature: float                 # 默认温度                                                                  │
│     max_retries: int = 3              # 最大重试                                                                   out_seconds: int = 120        # 超时                                                                       │
│                                                                                                                    │
│     async def execute(self, context: AgentContext) -> AgentResult                                                  │
│     async def build_messages(self, context: AgentContext) -> list[Message]                                         │
│     async def validate_outself, result: AgentResult) -> list[ValidationIssue]                                  │
│     async def on_retry(self, error: Exception, attempt: int) -> None                                               │
│                                                                                                                    │
│ 2.2.2 七 Agent 管线                                                                                                │
│                                                                                                              │
│ ┌──────────┬───────────────┬─────────────────────────────────────────────────┬────────┬────────────────────────┐   │
│ │  Agent   │     来源      │                      职责                       │  温  推荐模型        │   │
│ ├──────────┼───────────────┼─────────────────────────────────────────────────┼────────┼────────────────────────┤   │
│ │ Radar    │ InkOS         │ 分析当前写作状态，确定下一步任务、标记需注意的  │ 0.3    │ GPT-4o /ash  │   │
│ │          │               │ 问题                                            │        │                        │   │
│ ├──────────┼───────────────┼─────────────────────────────────────────────────┼────────┼────────────────────────┤   │
│ │ Architec │ InkOS         │ 结构规划：主线蓝图/分卷/章节/场景卡             │ 0.4    │ Claude Sonnet / GPT-4o │   │
│ │ t        │               │                                                 │        │                        │   │
│ ├──────────┼───────────────┼─────────────────────────────────────────────────┼â─────────────────────┤   │
│ │ Context  │ Webnovel      │ Hybrid RAG 检索 + POV 过滤 + 节奏建议注入       │ —      │ 非 LLM（纯工程逻辑）   │   │
│ │ Agent    │               │                                                 │        │                        │   │
│ ├──────────┼───────────────┼───────────────────â──────────────────────┼────────┼────────────────────────┤   │
│ │ Writer   │ InkOS 两阶段  │ Phase1: 创意写作(0.7) Phase2: 状态结算(0.3)     │ 0.7/0. │ Claude                 │   │
│ │          │               │                                                 │ 3      │ Sonnet（写作质量最佳） │   │
│ ├──────────┼â──────┼─────────────────────────────────────────────────┼────────┼────────────────────────┤   │
│ │ Settler  │ InkOS+Webnove │ Observer(提取事实) + Settler(更新真相文件) +    │ 0.2    │ Gemini                 │   │
│ │          │ l             │ 实体入库                                   │ Flash（快速低成本）    │   │
│ ├──────────┼───────────────┼─────────────────────────────────────────────────┼────────┼────────────────────────┤   │
│ │ Auditor  │ InkOS+Webnove │ 33 维度质量审计                                 │ 0.2    │ GPT-4o（ç稳定 │   │
│ │          │ l             │                                                 │        │ ）                     │   │
│ ├──────────┼───────────────┼─────────────────────────────────────────────────┼────────┼────────────────────────┤   │
│ │ Rer  │ InkOS 五模式  │ polish/rewrite/rework/spot-fix/anti-detect      │ 0.5    │ Claude Sonnet          │   │
│ └──────────┴───────────────┴─────────────────────────────────────────────────┴────────┴────────────────────────┘   │
│                                                                                                            │
│ 2.2.3 Pipeline DAG 执行器                                                                                          │
│                                                                                                                    │
│ 升级线性工作流为 DAG（有向无环图）执行引擎：                                                                       │
│                                                                                                      │
│ 支持能力：                                                                                                         │
│ ├── 拓扑排序：同层 Agent 并行执行                                                                                  │
│ ├── 条件分支：审计通过/不通过走不同路径                                                                            │
│ ├── 循环：Auditor →uditor（最多3轮）                                                                   │
│ ├── 人机中断点：可在任何节点前后插入人工审阅                                                                       │
│ ├── 断点恢复：每个节点执行结果持久化，崩溃后从最后完成的节点恢复                                                   │
│ └── 超时与降级：单 Agent 超时自动切换 fallback Provider                                                      │
│                                                                                                                    │
│ 全自动写一章的 DAG 配置：                                                                                          │
│                                                                                                                    │
│ radar → architect(chapter_brief)                                                                             │
│   → [并行] context_agent + pacing_controller.suggest()                                                             │
│     → writer_phase1 (创意写作)                                                                                     │
│       → writer_phase2 (状态结算)                                                                                   │
│         → settler (更新真相文件 + 实体入库)                                                                        │
│           → auditor (33维度审计)                                                                                   │
│             → [条件分支]                                                                                           │
│               ├─ [通过] → de_ai_engine → 完成                                                                      │
│               └─ [不通过] → reviser → auditor（循环，最多3轮）                                                   │
│                             └─ [3轮仍不通过] → 标记人工干预，暂停                                                  │
│                                                                                                                    │
│ 2.2.4 人机协作模式                                                                                                 │
│                                                                                                      │
│ 两种运行模式：                                                                                                     │
│                                                                                                                    │
│ 全自动模式： DAG 自动流转，仅在严重问题时暂停等待人工                                                              │
│ 半自动模式： 每个 Agent 输出后生成候选稿，等待人工审é»§续                                     │
│                                                                                                                    │
│ 中断点配置：                                                                                                       │
│ class HumanLoopPoint:                                                                                              │
│     trigger: str       # "always" | "on_low_score" | "on_first_run" | "never"                                      │
│     timeout_hours: float                                                                                           │
│     fallback: str      # "auto_accept" | "auto_reject" | "pause"                                                   │
│                                                                                                                    │
│ ---                                                                                                                │
│ 2.3 混合 RAG 引擎 (Hybrid RAG Engine)                                                                              │
│                                                                                                                    │
│ 设计来源： Webnovel Writer 的三通道 RAG                                                                            │
│                                                                                                                  1 三通道检索                                                                                                   │
│                                                                                                                    │
│ 查询文本 → [并行]                                                                                                  │
│   ├── 通道1: 向量检索 (pgvector)                                                                                   │
│Entity/MemoryEntry/Draft 的 embedding                                                                   │
│   │   余弦相似度 Top-K                                                                                             │
│   │                                                                                                                │
│   ├── 通道2: BM25 关键词检索 (rank_bm25)                                                                           │
│   │   + 设定文本建立 BM25 索引                                                                          │
│   │   精确名词匹配（角色名、地名、招式名）                                                                         │
│   │                                                                                                                │
│   └── 通道3: 图谱结构检索                                                                                          â实体关系图的 N 度路径检索                                                                                │
│       找到与当前 POV 角色相关的所有关联实体                                                                        │
│                                                                                                                    │
│ 2.3.2 融合与精排                                                                                                   │
│                                                                                                                    │
│ 三通道结果 → RRF 融合 (Reciprocal Rank Fusion)                                                                     │
│   score(d) = Σ 1/(k + rank_i(d))，k=60                                                                             │
│                                                                                                                    │
│ → 选 → Reranker 精排                                                                                       │
│   (BGE-Reranker-v2 或 Jina Reranker v3)                                                                            │
│                                                                                                                    │
│ → 最终 Top-M 结果注入上下文                                                                                        │
│                                                                                                      │
│ 2.3.3 上下文预算分配                                                                                               │
│                                                                                                                    │
│ 以 200K token 模型为例：                                                                                           │
│                                                                                                          │
│ ┌───────────────────────┬────────────┬───────┐                                                                     │
│ │         组件          │ Token 预算 │ 占比  │                                                                     │
│ ├───────────────────────┼──────────┼───────┤                                                                     │
│ │ System Prompt + Rules │ ~3,000     │ 1.5%  │                                                                     │
│ ├───────────────────────┼────────────┼───────┤                                                                     │
│ │ 世界设定摘要          │ ~500     │ 2.5%  │                                                                     │
│ ├───────────────────────┼────────────┼───────┤                                                                     │
│ │ POV 角色状态          │ ~3,000     │ 1.5%  │                                                                     │
│ ├────────────────────â───────┼───────┤                                                                     │
│ │ 前文摘要（最近5章）   │ ~8,000     │ 4%    │                                                                     │
│ ├───────────────────────┼────────────┼───────┤                                                                     │
│ │ 当前章已写内容    │ ~10,000    │ 5%    │                                                                     │
│ ├───────────────────────┼────────────┼───────┤                                                                     │
│ │ RAG 检索结果          │ ~5,000     │ 2.5%  │                                                                     │
│ ├───────────────────┼────────────┼───────┤                                                                     │
│ │ 场景卡 + 章节目标     │ ~2,000     │ 1%    │                                                                     │
│ ├───────────────────────┼────────────┼───────┤                                                                     │
│ │ 节奏/å        │ ~1,000     │ 0.5%  │                                                                     │
│ ├───────────────────────┼────────────┼───────┤                                                                     │
│ │ 输入合计              │ ~37,000    │ 18.5% │                                                                     │
│ ├──────────────────────┼───────┤                                                                     │
│ │ 输出预留              │ ~6,000     │ 3%    │                                                                     │
│ ├───────────────────────┼────────────┼───────┤                                                                     │
│ │ 安全裕量              │ ~150   │ 78.5% │                                                                     │
│ └───────────────────────┴────────────┴───────┘                                                                     │
│                                                                                                                    │
│ 渐进式上下文策略：                                                                                   │
│ - 第1-5章：注入完整设定 + 全部前文                                                                                 │
│ - 第6-20章：设定摘要 + 最近3章全文 + 更早章节摘要                                                                  │
│ - 第21章+：设定摘要 + 最近2章全文 + RAG 检索片段 + 真相文件快照                                                    │
│                                                                                                          │
│ ---                                                                                                                │
│ 2.4 质量审计系统 (Quality Audit System)                                                                            │
│                                                                                                                    │
│ 设计来源： InkOS 33 维度审计 + Webnovel 五维并行审查                                                     │
│                                                                                                                    │
│ 2.4.1 六大类 33 维度                                                                                               │
│                                                                                                                    │
│ 一致性 (Consistency) — 8 维                                                                                    │
│                                                                                                                    │
│ ┌─────┬─────────────────┬────────┬────────────────────────────────────────┐                                        │
│ │  #  │      维度       │  类型  │                  说明            │                                        │
│ ├─────┼─────────────────┼────────┼────────────────────────────────────────┤                                        │
│ │ 1   │ 角色设定冲突    │ LLM    │ 检查角色行为是否违反已锁定的设定       │                                        │
│ ├─────┼──â─┼────────┼────────────────────────────────────────┤                                        │
│ │ 2   │ 角色记忆违反    │ LLM    │ 角色是否知道了不该知道的事             │                                        │
│ ├─────┼─────────────────┼────────┼────────────────────────────────┤                                        │
│ │ 3   │ 世界观规则违反  │ LLM    │ 力量体系、物理法则是否被打破           │                                        │
│ ├─────┼─────────────────┼────────┼────────────────────────────────────────┤                                      │
│ │ 4   │ 时间线矛盾      │ LLM    │ 事件发生顺序是否自洽                   │                                        │
│ ├─────┼─────────────────┼────────┼────────────────────────────────────────┤                                        │
│ │ 5   │ 物资/道具连续性 │ 确定性 │ particle_ledger 中物品增å                                │
│ ├─────┼─────────────────┼────────┼────────────────────────────────────────┤                                        │
│ │ 6   │ 地理位置矛盾    │ LLM    │ 角色移动是否符合地理逻辑               │                                        │
│ ├─────┼────────â──┼────────────────────────────────────────┤                                        │
│ │ 7   │ 锁定属性违反    │ 确定性 │ AI 输出是否违反人工锁定的属性          │                                        │
│ ├─────┼─────────────────┼────────┼────────────────────────────┤                                        │
│ │ 8   │ 前后文逻辑矛盾  │ LLM    │ 因果链是否成立                         │                                        │
│ └─────┴─────────────────┴────────┴────────────────────────────────────────┘                                        │
│                                                                                                                  │
│ 叙事质量 (Narrative) — 7 维                                                                                        │
│                                                                                                                    │
│ ┌─────┬────────────────┬───────────────────────────────â                                                   │
│ │  #  │      维度      │                说明                │                                                      │
│ ├─────┼────────────────┼────────────────────────────────────┤                                                      │
│ │ 9   │ 大纲遵守度     │ 本章内容是否对应卷纲中的                                                │
│ ├─────┼────────────────┼────────────────────────────────────┤                                                      │
│ │ 10  │ 场景目标完成度 │ 场景卡中设定的目标是否达成         │                                                      │
│ ├─────┼───────────────────────────────────────┤                                                      │
│ │ 11  │ 章节钩子有效性 │ 章尾是否留有有效悬念               │                                                      │
│ ├─────┼────────────────┼────────────────────────────────────┤                                                    │
│ │ 12  │ 信息密度       │ 是否过疏（水文）或过密（信息轰炸） │                                                      │
│ ├─────┼────────────────┼────────────────────────────────────┤                                                      │
│ │ 13  │ 节奏感         │ 叙述-对话-描写-动作的比例是否合理  │                                                  │
│ ├─────┼────────────────┼────────────────────────────────────┤                                                      │
│ │ 14  │ 悬念维持       │ 已建立的悬念是否在本章得到延续     │                                                      │
│ ├─────┼──────────────â──────────────────────┤                                                      │
│ │ 15  │ 对话/叙述比例  │ 对话和叙述的比例是否适当           │                                                      │
│ └─────┴────────────────┴────────────────────────────────────┘                                                                                                                                                               │
│ 角色 (Character) — 6 维                                                                                            │
│                                                                                                                    │
│ ┌─────┬────────────────┬──────────────────────â───────┐                                                          │
│ │  #  │      维度      │              说明              │                                                          │
│ ├─────┼────────────────┼────────────────────────────────┤                                                          │
│ │ 16  │ OOC 检测       │ 角色言行æºº设           │                                                          │
│ ├─────┼────────────────┼────────────────────────────────┤                                                          │
│ │ 17  │ 角色弧线推进   │ 角色是否有成长/变化            │                                                          │
│ ├─────┼───────â─┼────────────────────────────────┤                                                          │
│ │ 18  │ 关系演变合理性 │ 角色间关系变化是否有铺垫       │                                                          │
│ ├─────┼────────────────┼────────────────────────────────┤                                                          │
│ │ 19  │ 对话风格一致性 │ 每个角色的说话方式是否保持特色 │                                                          │
│ ├─────┼────────────────┼────────────────────────────────┤                                                          │
│ │ 20  │ 情感弧线连贯性 │ 情感变化是否有递进逻辑                                                        │
│ ├─────┼────────────────┼────────────────────────────────┤                                                          │
│ │ 21  │ 角色能力边界   │ 角色是否超出已建立的能力范围   │                                                          │
│ └─────┴─────────────â───────────────────────────┘                                                          │
│                                                                                                                    │
│ 结构 (Structure) — 4 维                                                                                            │
│                                                                                                             ───┬────────────────┬────────────────────────────────┐                                                          │
│ │  #  │      维度      │              说明              │                                                          │
│ ├─────┼────────────────┼─────────────────────────â                                                         │
│ │ 22  │ 伏笔埋设与回收 │ pending_hooks 状态是否合理推进 │                                                          │
│ ├─────┼────────────────┼────────────────────────────────┤                                                          │
│ │ 23  │ 支线进度       │ 各支线是否停滞过久         │                                                          │
│ ├─────┼────────────────┼────────────────────────────────┤                                                          │
│ │ 24  │ 全书节奏曲线   │ Strand Weave 比例是否健康      │                                                          │
│ ├─────┼───────────â¼────────────────────────────────┤                                                          │
│ │ 25  │ 章节内三幕结构 │ 起-承-转 结构是否清晰          │                                                          │
│ └─────┴────────────────┴────────────────────────────────┘                                                    │
│                                                                                                                    │
│ 风格 (Style) — 4 维                                                                                                │
│                                                                                                                    │
│ ┌─────┬──────────────┬────────────â───────┐                                                          │
│ │  #  │     维度     │               说明               │                                                          │
│ ├─────┼──────────────┼──────────────────────────────────┤                                                          │
│ │ 26  │ AI 痕迹检测  │ 疲劳词、å          │                                                          │
│ ├─────┼──────────────┼──────────────────────────────────┤                                                          │
│ │ 27  │ 重复表达检测 │ 相邻段落是否用了相同表达         │                                                          │
│ ├─────┼────────â─────────────────────────────┤                                                          │
│ │ 28  │ 禁用词句检测 │ 是否使用了 book_rules 中的禁用词 │                                                          │
│ ├─────┼──────────────┼──────────────────────────────────┤                                                          │
│ │ 29  │ 风格一致性   │ 是否与 style_preset 保持一致     │                                                          │
│ └─────┴──────────────┴──────────────────────────────────┘                                                          │
│                                                                                                      │
│ 爽点 (Engagement) — 4 维（来自 Webnovel Writer）                                                                   │
│                                                                                                                    │
│ ┌─────┬────────────────┬────────────────────────────────────────────────────────────────┐                        │
│ │  #  │      维度      │                               说明                               │                        │
│ ├─────┼────────────────┼──────────────────────────────────────────────────────────────────┤                        │
│ │ 30  │ 爽点密å¯章 ≥ 1 个爽点                                                  │                        │
│ ├─────┼────────────────┼──────────────────────────────────────────────────────────────────┤                        │
│ │ 31  │ 爽点模式识别   │ 6种模式：装逼打脸/扮猪吃虎/越级反杀/打脸权å¦/甜蜜超预期 │                        │
│ ├─────┼────────────────┼──────────────────────────────────────────────────────────────────┤                        │
│ │ 32  │ 高潮对齐大纲   │ 爽点是否出现在大纲规划的位置                                     │                        │
│ â────┼────────────────┼──────────────────────────────────────────────────────────────────┤                        │
│ │ 33  │ 读者钩子有效性 │ 章尾钩子是否能让读者想继续读                                     │                        │
│ └─────┴────────────â─────────────────────────────────────────────────────────────────┘                        │
│                                                                                                                    │
│ 2.4.2 审计执行流程                                                                                                 │
│                                                                                                      │
│ class AuditRunner:                                                                                                 │
│     async def audit_chapter(self, chapter_id, mode="full") -> AuditReport:                                         │
│         """                                                                                                        │
│         mode:                                                                                                      │
│           "full" → 全量 33 维度                                                                                    │
│           "incremental" → 仅对修改部分执行相关维度                                                                 │
│           "quick" → 仅执行确定性检查 (5/7/26/27/28)                                                                │
│                                                                                                              │
│         执行方式：                                                                                                 │
│           确定性检查 → 并行执行（零 LLM 成本）                                                                     │
│           LLM 检查 → 按类别分组并行调用                                                                            │
│         """                                                                                                        │
│                                                                                                                    │
│ 审计评分体系：                                                                                                     │
│ - 每个维度评分 0-10                                                                                                │
│ - 严重度分级：pass(≥7) / warning(4-6) / er / blocking(0)                                                   │
│ - 存在任何 blocking → 必须修订                                                                                     │
│ - 总分 ≥ 28/33 → 非阻塞问题，可选修订                                                                              │
│ - 总分 < 20/33 → 需要 rework 级重写                                                                                │
│                                                                                                      │
│ ---                                                                                                                │
│ 2.5 状态管理系统 (7+3 真相文件)                                                                                    │
│                                                                                                                    │
│ 设计来源： InkOS 真相文件体系                                                                            │
│                                                                                                                    │
│ 2.5.1 十个真相文件                                                                                                 │
│                                                                                                                    │
│ ┌───────────────────┬──────────────────────────────────────┬────────────────────────┐                  │
│ │       文件        │                       职责                       │        更新频率        │                  │
│ ├───────────────────┼─────────────────────────────────â────────┼────────────────────────┤                  │
│ │ story_bible       │ 不可变核心设定（世界观、力量体系、历史）         │ 项目初始化时，极少修改 │                  │
│ ├───────────────────┼──────────────────────────────────────────────────┼──────────────────┤                  │
│ │ volume_outline    │ 分卷结构（每卷核心冲突、关键转折、章节范围）     │ 每卷开始时             │                  │
│ ├───────────────────┼──────────────────────────────────────────────────┼───────────────────â───┤                  │
│ │ book_rules        │ 三层规则：基础护栏 + 题材规则 + 本书定制规则     │ 项目初始化时           │                  │
│ ├───────────────────┼──────────────────────────────────────────────────┼────────────────────────┤                  │
â current_state     │ 当前全局状态快照（角色位置、关系状态、已知信息） │ 每章写完后             │                  │
│ ├───────────────────┼──────────────────────────────────────────────────┼────────────────────────┤                  │
│ │ particle_ledger   │ 物资/é¸ª（增减记录、期末值）           │ 每章写完后             │                  │
│ ├───────────────────┼──────────────────────────────────────────────────┼────────────────────────┤                  │
│ │ pending_hooks     │ 未回收伏笔池（描述、埋设章节、预期回收时机ï           │                  │
│ ├───────────────────┼──────────────────────────────────────────────────┼────────────────────────┤                  │
│ │ chapter_summaries │ 全部已写章节的压缩摘要                           │ 每章写完后             │                  │
│ ├───────┼──────────────────────────────────────────────────┼────────────────────────┤                  │
│ │ subplot_board     │ 支线状态看板（A/B/C 线进度、停滞检测）           │ 每章写完后             │                  │
│ ├───────────────────┼───────â─────────────────────────────────┼────────────────────────┤                  │
│ │ emotional_arcs    │ 角色情感弧线追踪（情感状态、强度、变化趋势）     │ 每章写完后             │                  │
│ ├───────────────────┼────────────────────────────â────────────────────┼────────────────────────┤                  │
│ │ character_matrix  │ 角色交互矩阵 + 信息边界（谁知道什么、谁见过谁）  │ 每章写完后             │                  │
│ └───────────────────┴─────────────────────────────────────────â───────┴────────────────────────┘                  │
│                                                                                                                    │
│ 2.5.2 状态更新协议                                                                                                 │
│                                                                                                                    │
│ 每章写ettler Agent 执行原子更新：                                                                        │
│                                                                                                                    │
│ Writer Phase2 输出 → Observer 子任务                                                                               │
│   ├── 提取角色出场和位置变化                                                                                       │
│   ├资源的获得/损失                                                                                     │
│   ├── 提取信息获知者和知识边界变化                                                                                 │
│   ├── 提取伏笔的埋设和推进                                                                                         │
│   ├── 提取情感强度变化                                                                                 │
│   └── 提取支线进展                                                                                                 │
│                                                                                                                    │
│ → Settler 子任务                                                                                                   │
│   ├── 对比 current_state，计算 diff                                                                      │
│   ├── 原子更新所有受影响的真相文件                                                                                 │
│   ├── 版本号递增，保留历史可回溯                                                                                   │
│   └── 新实体入库（置信度判断）                                                                                     │
│                                                                                                                    │
│ ---                                                                                                                │
│ 2.6 节奏控制系统 (Pacing Control — Strand Weave)                                                                   │
│                                                                                                                    │
│ 设计来源： Webnovel Writer 的三线交织系统                                                                    │
│                                                                                                                    │
│ 2.6.1 三线交织模型                                                                                                 │
│                                                                                                                    │
│ ┌───────────────┬────────────┬──â────────────────────────────┐                                       │
│ │    Strand     │    含义    │ 目标占比 │               内容               │                                       │
│ ├───────────────┼────────────┼──────────┼──────────────────────────────────┤                                 │
│ │ Quest         │ 主线推进   │ 60%      │ 主冲突推进、关键转折、里程碑事件 │                                       │
│ ├───────────────┼────────────┼──────────┼──────────────────────────────────┤                                       │
│ │ Fire          │ 冲突与爽点 │ 20%    爽点模式、冲突升级、高潮事件  │                                       │
│ ├───────────────┼────────────┼──────────┼──────────────────────────────────┤                                       │
│ │ Constellation │ 角色与情感 │ 20%      │ 关系演变、角色成长、情感高潮     │                                      ───────┴────────────┴──────────┴──────────────────────────────────┘                                       │
│                                                                                                                    │
│ 2.6.2 爽点密度基准                                                                                                 │
│                                                                                                      │
│ - 每章 ≥ 1 个 cool-point                                                                                           │
│ - 每 5 章 ≥ 1 个 combo（2种以上爽点模式叠加）                                                                      │
│ - 每 10 章 ≥ 1 个 milestone victory（改变主角地位的里程碑）                                                        │
│                                                                                                              │
│ 6种爽点执行模式：                                                                                                  │
│ 1. 装逼打脸（Flex & Counter）                                                                                      │
│ 2. 扮猪吃虎（Underdog Reveal）                                                                                     │
│ 3. 越级反æy）                                                                                    │
│ 4. 打脸权威（Authority Challenge）                                                                                 │
│ 5. 反派翻车（Villain Downfall）                                                                                    │
│ 6. 甜蜜超预期（Sweet Surprise）                                                                                    │
│                                                                                                            │
│ 2.6.3 红线规则                                                                                                     │
│                                                                                                                    │
│ - Quest 连续不超过 5 章 → 否则强制插入 Fire/Constellation                                                          │
│ - Fire 断档不超过 3 章 → 否å²突升级                                                                          │
│ - 情感弧线连续 4 章低迷 → 触发情感转折事件                                                                         │
│ - 每章至少包含 2 种 Strand                                                                                         │
│                                                                                                                    │
│ 2.6.4 节奏建议注å                                                                                           │
│                                                                                                                    │
│ PacingController 在 Context Agent 组装上下文时，分析历史 pacing_meta 数据，自动生成下一章的节奏建议，注入 Writer   │
│ Agent 的 Prompt：                                                                                                  │
│                                                                                                                    │
│ 【节奏建议】                                                                                                       │
│ - 当前 Quest 已连续 4 章，建议本章加入 Fire 事件                                                                   │
│ - 上一章 combo 爽点后，本章可适当降速，发展 Constellation 线                                                       停滞 6 章，建议本章推进                                                                                   │
│                                                                                                                    │
│ ---                                                                                                                │
│ 2.7 去 AI 味引擎 (De-AI Engine)                                                                                    │
│                                                                                                        │
│ 设计来源： InkOS 系统化去 AI 味方案                                                                                │
│                                                                                                                    │
│ 2.7.1 四层处理                                                                                                     │
│                                                                                                                    │
│ 第一层：预防（Writer Prompt 层面）                                                                                 │
│ - 嵌入 200+ 疲劳词禁用表（"值得注意的是""不禁""缓缓""映入眼帘""嘴角微微上扬"...）                                  │
│ - 嵌入禁用句式正则（"他深知...""...划破了寂静""在这个过程中..."）                                             面引导：鼓励具体感官细节、独特比喻、口语化表达                                                                 │
│                                                                                                                    │
│ 第二层：检测（Auditor 维度 #26）                                                                                   │
│ class AIDetector:                                                                                                 ue_words: list[str]          # 200+ 疲劳词表                                                              │
│     banned_patterns: list[re.Pattern] # 禁用句式正则                                                               │
│     dialogue_fingerprints: dict       # 每个角色的用词频率分布                                                     │
│                                                                                                                    │
│     def f, text) -> list[AITrace]:                                                                       │
│         # 返回所有 AI 痕迹位置、类型和严重度                                                                       │
│                                                                                                                    │
│ 第三层：修订（Reviser anti-detect 模式）                                                                           │
│ - 替换疲å                                                                                         │
│ - 重写千篇一律的句式                                                                                               │
│ - 调整对话以匹配角色个性指纹                                                                                       │
│ - 增加语义噪声（不影响情节的个性化细节）                                                                           │
│                                                                                                                  │
│ 第四层：统计（全局追踪）                                                                                           │
│ - 追踪每章 AI 痕迹密度趋势                                                                                         │
│ - 生成去 AI 味报告                                                                                                 │
âriter Prompt 持续优化禁用表                                                                              │
│                                                                                                                    │
│ ---                                                                                                                │
│ 2.8 三层规则体系（来自 InkOS）                                                                                     │
│                                                                                                                  │
│ 第一层：基础护栏（~25 条，所有题材通用）                                                                           │
│                                                                                                                    │
│ 人物塑造：                                                                                                         │
│ - 性格一为约束                                                                                             │
│ - 对话必须体现角色个性差异                                                                                         │
│ - 展示而非告知（show don't tell）                                                                                  │
│                                                                                                                    │
│ 叙事技法ï                                                                                                 │
│ - 冲突驱动，每个场景推进至少一个冲突                                                                               │
│ - 节奏控制，张弛有度                                                                                               │
│ - 描写包含至少两种感官细节                                                                                         │
â                                                                                                        │
│ 逻辑自洽：                                                                                                         │
│ - 因果链完整                                                                                                       │
│ - 伏笔有埋有收                                                                                                     │
│                                                                                                                    │
│ 语言约束：                                                                                                         │
│ - 禁用疲劳词表                                                                                                     │
│ - 禁用句式列表                                                                                                     │
│ - 不在叙述中                                                                                   │
│                                                                                                                    │
│ 第二层：题材特性（Genre Profile）                                                                                  │
│                                                                                                                    │
│ 预置题材模板（可扩展）：                                                                               │
│                                                                                                                    │
│ ┌─────────────────┬────────────────────────────────────────────────────────────┐                                   │
│ │      题材       │                      特有规则                          │                                   │
│ ├─────────────────┼────────────────────────────────────────────────────────────┤                                   │
│ │ 玄幻 (xuanhuan) │ 力量等级体系、修为突破逻辑、法宝规则、numericalSystem=true │                                 │
│ ├─────────────────┼────────────────────────────────────────────────────────────┤                                   │
│ │ 仙侠 (xianxia)  │ 道法体系、门派政治、因果轮回、powerScaling=true            │                                   │
│ ├─────────────────┼â────────────────────────────────────────────────┤                                   │
│ │ 都市 (urban)    │ 现实约束、禁止超自然元素混入、职场/感情线索                │                                   │
│ ├─────────────────┼────────────────────────────────────â───────┤                                   │
│ │ 恐怖 (horror)   │ 氛围营造技法、心理恐惧优先、信息缓释                       │                                   │
│ ├─────────────────┼────────────────────────────────────────────────────────────┤                                   │
│ │ 科幻scifi)    │ 科技硬设定、物理规律约束、eraResearch=true                 │                                   │
│ ├─────────────────┼────────────────────────────────────────────────────────────┤                                   │
│ │ 言情 (romance)  │ 情感节奏、关系递进规则、甜蜜/虐心比例                    │                                   │
│ ├─────────────────┼────────────────────────────────────────────────────────────┤                                   │
│ │ 其他 (custom)   │ 用户自定义规则集                                           │                                   │
│ └────────────â─┴────────────────────────────────────────────────────────────┘                                   │
│                                                                                                                    │
│ 每个题材 Profile 包含：                                                                                            │
│ - 该题材特有的禁å                                                                                   │
│ - 审计维度启用/禁用列表                                                                                            │
│ - 数值体系开关                                                                                                     │
│ - 战力等级开关                                                                                                     │
│ - 年代考据需求开关                                                                                     │
│                                                                                                                    │
│ 第三层：本书规则（Book Rules）                                                                                     │
│                                                                                                                    │
│ 每个项目的个性化规则：                                                                                   │
│                                                                                                                    │
│ protagonist:                                                                                                       │
│   name: "叶辰"                                                                                                     │
│   personality_lock: ["冷傲", "理性", "利己"]                                                                       │
│   behavioral_constraints:                                                                                          │
│     - "绝不会主动帮助不认识的人"                                                                                   │
│     - "面对强者时保持冷静，不会冲动"                                                                               │
│     - "重视承诺，但只对认可的人"                                                                       │
│     - "遇到机缘时优先考虑自身利益"                                                                                 │
│     - "不会轻易暴露底牌"                                                                                           │
│                                                                                                                    │
│ taboos:                                                                                                  │
│   - "主角不会哭"                                                                                                   │
│   - "不出现现代科技产品"                                                                                           │
│                                                                                                                    │
│ numerical_hard_cap:                                                                                    │
│   cultivation_max: "元婴期"                                                                                        │
│                                                                                                                    │
│ resource_types:                                                                                                    │
│   - "灵石"                                                                                               │
│   - "丹药"                                                                                                         │
│   - "法器"                                                                                                         │
│                                                                                                                    │
│ custom_audit_dimensions:                                                                                           "修为突破必须有合理铺垫（至少2章前开始暗示）"                                                                  │
│                                                                                                                    │
│ ---                                                                                                                │
│ 三、AI 写作管线完整工作流                                                                                                                                                                                                     │
│ 3.1 从创意到完稿的五个阶段                                                                                         │
│                                                                                                                    │
│ 阶段1: 项目初始化 ──────────────────────────────                                                       │
│   输入: 题材、风格、目标字数、核心创意（一句话梗概）                                                               │
│   执行: Architect Agent                                                                                            │
│   输出: story_bible + book_rules                                                                                   │
│   人机: ★ 必须人工确认                                                                                   │
│                                                                                                                    │
│ 阶段2: 主线规划 (Think) ────────────────────────                                                                   │
│   输入: story_bible + book_rules                                                                                   │
│   执行: Architect Agent                                                                                        │
│   输出: plot_blueprint（主线蓝图）+ volume_outline（分卷计划）                                                     │
│   人机: ★ 候选稿选择（可生成多个方案对比）                                                                         │
│                                                                                                                    │
│ 阶段3: 分卷分章 (Tissue──────────                                                                    │
│   输入: plot_blueprint + volume_outline                                                                            │
│   执行: Architect Agent（逐卷展开）                                                                                │
│   输出: chapters（章节列表）+ scene_cards（场景卡）                                                                │
│   人机: 可æ整                                                                                   │
│                                                                                                                    │
│ 阶段4: 逐章生成 (循环) ────────────────────────                                                                    │
│                                                                                                                    │
│   4a. 侦察 → Radar Agent                                                                                           │
│       分析当前进度、下一章重点、需注意的问题                                                                       │
│       输出: chapter_brief（章节简报）                                                                              │
│                                                                                                        │
│   4b. 上下文组装 → Context Agent（非 LLM）                                                                         │
│       执行: Hybrid RAG 检索 + POV 过滤 + 节奏建议注入                                                              │
│       输出: assembled_context                                                                                      │
│                                                                                                                创意写作 → Writer Agent Phase1 (temperature=0.7)                                                             │
│       输入: assembled_context + scene_card + style_preset                                                          │
│       输出: raw_draft                                                                                              │
│                                                                                                                    │
│   4d. 状态结er Agent Phase2 (temperature=0.3) → Settler                                                   │
│       输入: raw_draft + 当前真相文件                                                                               │
│       输出: 更新后的 10 个真相文件 + 新实体入库                                                                    │
│                                                                                                                    │
│   4e. 质量审tor Agent                                                                                     │
│       输入: raw_draft + truth_files + book_rules                                                                   │
│       输出: audit_report（33 维度评分 + 问题清单）                                                                 │
│                                                                                                                    │
│   4f. 修订循环 → Revient（最多3轮）                                                                          │
│       条件: audit_report 中有 blocking 问题                                                                        │
│       模式: 根据问题类型自动选择 polish/rewrite/rework/spot-fix                                                    │
│       输出: revised_draft                                                                                          │
│                                                                                                                  │
│   4g. 去 AI 味 → De-AI Engine + Reviser anti-detect 模式                                                           │
│       输入: revised_draft + fatigue_words + dialogue_fingerprints                                                  │
│       输出: final_draft                                                                                            │
│                                                                                                                  │
│   4h. 记忆回填 → Settler                                                                                           │
│       更新: chapter_summaries, embedding 索引                                                                      │
│                                                                                                                    │
│ 阶段5: 卷末检查 ────────────────                                                                     │
│   执行: Auditor Agent（卷级审计）                                                                                  │
│   检查: 支线收束率、伏笔回收率、角色弧线完整性、节奏曲线                                                           │
│   人机: 展示卷级报告，决定是否需要调整后续卷的计划                                                                                                                                                                          │
│ 3.2 Writer Agent Prompt 结构示例                                                                                   │
│                                                                                                                    │
│ [SYSTEM]                                                                                                           │
│ 你是一位专注ä}的小说作家。                                                                                  │
│                                                                                                                    │
│ ## 写作风格                                                                                                        │
│ {style_preset_content}                                                                                             │
│                                                                                                                │
│ ## 规则（必须严格遵守）                                                                                            │
│                                                                                                                    │
│ ### 基础护栏                                                                                                       │
│ {base_guardrails_25_rules}                                                                             │
│                                                                                                                    │
│ ### 题材规则                                                                                                       │
│ {genre_profile_content}                                                                                            │
│                                                                                                            │
│ ### 本书规则                                                                                                       │
│ {book_rules_yaml}                                                                                                  │
│                                                                                                                    │
│ ## 禁止                                                                                                │
│ - 不使用以下词语：{fatigue_words_top_100}                                                                          │
│ - 不使用以下句式：{banned_patterns_top_30}                                                                         │
│                                                                                                                    │
│ ## 要求                                                                                                        │
│ - 每个场景必须推进至少一个冲突                                                                                     │
│ - 对话必须体现角色个性差异                                                                                         │
│ - 描写必须包含至少两种感官细节                                                                                     │
│ - 展示而非告知                                                                                         │
│                                                                                                                    │
│ [USER]                                                                                                             │
│ ## 当前章节目标                                                                                                    │
│ {chapter_brief}                                                                                                                                                                                                               │
│ ## 场景卡                                                                                                          │
│ {scene_card_content}                                                                                               │
│                                                                                                                    │
│ ## POV 角色当                                                                                       │
│ {pov_character_state_from_current_state}                                                                           │
│                                                                                                                    │
│ ## 前文摘要（仅 POV 角色所知）                                                                                     │
│ {pov_filtered_chapter_summaries}                                                                             │
│                                                                                                                    │
│ ## 相关设定（自动检索）                                                                                            │
│ {rag_retrieved_worldbook_entries}                                                                                  │
│                                                                                                                │
│ ## 角色对话指纹                                                                                                    │
│ {dialogue_fingerprints_for_appearing_characters}                                                                   │
│                                                                                                                    │
│ ## 节奏建议                                                                                                    │
│ {pacing_suggestion}                                                                                                │
│                                                                                                                    │
│ ## 任务                                                                                                            │
│ 请基于以上信息写出本场景的正文。字数目标：{target_words}字。                                                     │
│ 直接输出小说正文，不要任何元数据或标注。                                                                           │
│                                                                                                                    │
│ 3.3 防幻觉三定律（来自 Webnovel Writer）                                                                           │
│                                                                                                        │
│ 贯穿整个管线的核心约束：                                                                                           │
│                                                                                                                    │
│ 1. 大纲即法律：Writer Agent 的输出必须严格对应 volume_outline 中当前章节的剧情节点，不可跳过或提前消耗             │
│ 2. 设定即物理：世界观规则（力é构）不可被 AI 随意修改，违反即为 blocking 级审计问题              │
│ 3. 发明需识别：AI 输出中出现的新实体（人名、地名、物品）必须经过 Settler 识别入库，不能"悄悄"引入未管理的设定      │
│                                                                                                                    │
│ ---                                                                                                                │
│ å设计                                                                                                   │
│                                                                                                                    │
│ 4.1 核心实体关系图                                                                                                 │
│                                                                                                                    │
│ Project (项目)                                                                                             │
│ ├── 1:N → Volume (分卷)                                                                                            │
│ │         └── 1:N → Chapter (章节)                                                                                 │
│ │                   ├── 1:N → SceneCard (场景卡)                                                                   │
│ │        ── 1:N → Draft (草稿/候选稿)                                                                  │
│ │                   ├── 1:1 → MemoryEntry (章节记忆)                                                               │
│ │                   ├── 1:N → AuditRecord (审计记录)                                                               │
│ │                   └── 1:1 → PacingMeta (节奏元数据)                                                          │
│ │                                                                                                                  │
│ ├── 1:N → Entity (实体)                                                                                            │
│ │         └── N:N → Relationship (关系)                                                                            │
│ │                                                                                                            1:N → TruthFile (10个真相文件)                                                                                 │
│ ├── 1:1 → BookRules (本书规则)                                                                                     │
│ ├── 1:N → Worldbook (世界书条目)                                                                                   │
│ ├── 1:N → StylePreset (风格预设)                                                                         │
│ ├── 1:N → Hook (伏笔/钩子)                                                                                         │
│ └── 1:N → OutlineCandidate (大纲候选稿)                                                                            │
│                                                                                                                    │
│ 全局表:                                                                                                    │
│ ├── ProviderConfig (模型提供商配置)                                                                                │
│ ├── WorkflowPreset (工作流模板)                                                                                    │
│ ├── UsageRecord (用量/成本追踪)                                                                                    │
│ └── JobRun (任务执行记录)                                                                                  │
│                                                                                                                    │
│ 4.2 关键新增表 Schema                                                                                              │
│                                                                                                                    │
│ -- 分卷                                                                                                  CREATE TABLE volumes (                                                                                             │
│     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),                                                                 │
│     project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,                                            │
│     title VARCHAR(200) NOT NULL,                                                                                   │
│     objective TEXT NOT NULL,           -- 本卷核心冲突                                                             │
│     climax_hint TEXT,                  -- 本卷高潮预告                                                             │
│     sort_order INTEGER NOT NULL DEFAULT 1,                                                                         │
│     created_at TIMESTAMPTZ NOT NULL DEFAULT now(),                                                                 │
│     updated_at TIMESTAMPTZ NDEFAULT now()                                                                  │
│ );                                                                                                                 │
│                                                                                                                    │
│ -- 实体                                                                                                            │
│ CREATE TABLE entities (                                                                                        │
│     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),                                                                 │
│     project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,                                            │
│     name VARCHAR(200) NOT NULL,                                                                                    │
│     aliases JSONB NOT NULL DEFAULT '[]',                                                                           │
│     entity_type VARCHAR(50) NOT NULL,   -- character/location/faction/item/concept/power_system                    │
│     attributes JSONB NOT NULL DEFAULT '{}',                                                                        │
│     locked_attributes JSONB NOT NULL DEFAULT '{}',                                                                 │
│     knowledge_boundary JSONB NOT NULL DEFAULT '{}',                                                                │
│     embedding vector(1536),                                                                                        │
│     confidence FLOAT NOT NULL DEFAULT 1.0,                                                                         │
│     source VARCHAR(20) NOT NULL DEFAULT 'manual',                                                                  │
│     created_at TIMESTAMPTZ NOT NULL DEFAULT now(),                                                                 │     updated_at TIMESTAMPTZ NOT NULL DEFAULT now()                                                                  │
│ );                                                                                                                 │
│                                                                                                                    │
│ -- 实体关系                                                                                                        │
│ CREATE TABLE reips (                                                                                       │
│     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),                                                                 │
│     project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,                                            │
│     source_entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,                                      │
│     target_entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,                                      │
│     relation_type VARCHAR(50) NOT NULL,                                                                            │
│     attributes JSONB NOT NULL DEFAULT '{}',                                                                        │
│     valid_from_chapter_id UUID REFERENCES chapters(id),                                                            │
│     valid_to_chapter_id UUID REFERENCES chapters(id),                                                              │
│     created_at TIMESTAMPTZ NOT NULL DEFAULT now()                                                                  │
│ );                                                                                                                 │
│                                                                                                                    │
│ -- 真相文件（版本化）                                                                                            │
│ CREATE TABLE truth_files (                                                                                         │
│     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),                                                                 │
│     project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,                                            │
│     file_type VARCHAR(50) NOT NULL,                                                                                │
│     content JSONB NOT NULL DEFAULT '{}',                                                                           │
│     version INTEGER NOT NULL DEFAULT 1,                                                                            │
│     updated_by_chapter_id UUID REFERENCES chapters(id),                                                            │
│     created_at TIMESTAMPTZ NOT NULL DEFAULT now(),                                                                 â     updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),                                                                 │
│     UNIQUE (project_id, file_type)                                                                                 │
│ );                                                                                                                 │
│                                                                                                                    │
│ -- 真相文件                                                                                      │
│ CREATE TABLE truth_file_history (                                                                                  │
│     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),                                                                 │
│     truth_file_id UUID NOT NULL REFERENCES truth_files(id) ON DELETE CASCADE,                                      │
│     version INTEGER NOT NULL,                                                                                      │
│     content JSONB NOT NULL,                                                                                        │
│     changed_by_chapter_id UUID REFERENCES chapters(id),                                                            │
│     created_at TIMESTAMPTZ NOT NULL DEFAULT now()                                                                  │
│ );                                                                                                                 │
│                                                                                                                    │
│ -- 场景卡                                                                                                          │
│ CREATE TABLE scene_cards (                                                                                         │
│     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),                                                           │
│     chapter_id UUID NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,                                            │
│     sort_order INTEGER NOT NULL DEFAULT 1,                                                                         │
│     pov_character_id UUID REFERENCES entities(id),                                                                 │
│     location VARCHAR(200),                                                                                         │
│     time_marker VARCHAR(100),                                                                                      │
│     goal TEXT NOT NULL,                 -- 场景目标                                                                │
│     conflict TEXT,                      -- 场景冲突                                                                │
│     outcome TEXT,                       -- 预期结果                                                                │
âers JSONB NOT NULL DEFAULT '[]',  -- 出场角色ID列表                                                     │
│     notes TEXT,                         -- 额外提示                                                                │
│     created_at TIMESTAMPTZ NOT NULL DEFAULT now()                                                                  │
│ );                                                                                                                 │
│                                                                                                                │
│ -- 审计记录                                                                                                        │
│ CREATE TABLE audit_records (                                                                                       │
│     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),                                                                 │
│     chapter_id UUID NOT NULL REFERENCESs(id) ON DELETE CASCADE,                                            │
│     draft_id UUID NOT NULL REFERENCES drafts(id) ON DELETE CASCADE,                                                │
│     dimension VARCHAR(50) NOT NULL,     -- 审计维度名                                                              │
│     category VARCHAR(30) NOT NULL,      -- consistency/narrative/character/structure/style/engagement              │
│     score FLOAT NOT NULL,               -- 0-10                                                          │
│     severity VARCHAR(20) NOT NULL,      -- pass/warning/error/blocking                                             │
│     message TEXT NOT NULL,                                                                                         │
│     evidence JSONB NOT NULL DEFAULT '[]',                                                                          │
│     created_at TIMESTAMPTZ NOT NULL DEFAULT now()                                                                  │
│ );                                                                                                                 │
│                                                                                                                    │
│ -- 伏笔/钩子                                                                                                       │
│ CREATE TABLE hooks (                                                                                        
│     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),                                                                 │
│     project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,                                            │
│     hook_type VARCHAR(20) NOT NULL,     -- foreshadow/cliffhanger/chekhov_gun                                      │
│     description TEXT NOT NULL,                                                                                     │
│     planted_chaer_id UUID NOT NULL REFERENCES chapters(id),                                                      │
│     expected_resolve_chapter VARCHAR(100),  -- 预期回收时机                                                        │
│     resolved_chapter_id UUID REFERENCES chapters(id),                                                              │
│     status VARCHAR(20) NOT NULL DEFAULT 'open',  -- open/resolved/abandoned                                        │
│     created_at TIMESTAMPTZ NOT  now()                                                                  │
│ );                                                                                                                 │
│                                                                                                                    │
│ -- 节奏元数据                                                                                                      │
│ CREATE TABLE pacing_meta (                                                                               │
│     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),                                                                 │
│     chapter_id UUID NOT NULL UNIQUE REFERENCES chapters(id) ON DELETE CASCADE,                                     │
│     quest_ratio FLOAT,                                                                                             │
│     fire_ratio FLOAT,                                                                                              │
│     constellation_ratio FLOAT,                                                                                     │
│     highlight_count INTEGER NOT NULL DEFAULT 0,                                                                    │
│     highlight_types JSONB NOT NULL DEFAULT '[]',                                                                   │
│     tension_level FLOAT,                -- 0.0 ~ 1.0                                                               │
│     strand_tags JSONB NOT NULL DEFAULT '[]',  -- 本章包含的 strand 类型列表                                        │
│     created_at TIMESTAMPTZ NOT NULL DEFAULT now()                                                                  │
│ );                                                                                                                 │
│                                                                                                                    │
 chapters 表增强字段                                                                                             │
│ ALTER TABLE chapters ADD COLUMN volume_id UUID REFERENCES volumes(id);                                             │
│ ALTER TABLE chapters ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 1;                                             │
│ ALTER TABLE chapters ADD COLUMN pov_character_id UUID REFERENCES entities(id);                                     │
│ ALTER TABLE chaptLUMN timeline_position VARCHAR(100);                                                    │
│ ALTER TABLE chapters ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'planned';                                     │
│   -- planned / writing / draft_ready / audited / final / needs_revision                                            │
│                                                                                                                    │
│ -- drafts 表增强字段                                                                                     │
│ ALTER TABLE drafts ADD COLUMN generation_meta JSONB DEFAULT '{}';                                                  │
│   -- 记录: 使用的模型、温度、token消耗、耗时、Agent链路                                                            │
│ ALTER TABLE drafts ADD COLUMN audit_score FLOAT;                                                                   │
│ ALTER TABLE drafts ADD COLUMN content_embedding vecto);                                                      │
│                                                                                                                    │
│ 4.3 向量索引策略                                                                                                   │
│                                                                                                                    │
│ -- 实体 embedding 索引（HNSW，更快的近似搜索）                                                             │
│ CREATE INDEX idx_entities_embedding ON entities                                                                    │
│     USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);                                  │
│                                                                                                                    │
│ -- 草稿内容 embedding 索引                                                                             │
│ CREATE INDEX idx_drafts_embedding ON drafts                                                                        │
│     USING hnsw (content_embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);                          │
│                                                                                                                    │
│ -- 记忆条目 embedding 索引                                                                                 ALTER TABLE memory_entries ADD COLUMN embedding vector(1536);                                                      │
│ CREATE INDEX idx_memory_embedding ON memory_entries                                                                │
│     USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);                                  │
│                                                                                                                    │
│ Embedding 模型选æ                                                                                        │
│ - 首选：BGE-M3（中文语义检索最优，1024维）                                                                         │
│ - 备选：text-embedding-3-large（OpenAI，1536维，API调用简单）                                                      │
│ - 更新时机：每次 Settler 更新真相文件时同步更新相关 embedding                                                      │
â                                                                                                      │
│ ---                                                                                                                │
│ 五、部署与运维                                                                                                     │
│                                                                                                                    │
│ 5.1 Docker Compose 配置                                                                                          │
│                                                                                                                    │
│ services:                                                                                                          │
│   postgres:                                                                                                        │
│     image: pgvector/pgvector:pg17      # 内çector 扩展                                                        │
│     environment:                                                                                                   │
│       POSTGRES_USER: aiwriter                                                                                      │
│       POSTGRES_PASSWORD: ${DB_PASSWORD}                                                                            │
│       POSTGRES_DB: aiwriter                                                                                    │
│     ports: ["5432:5432"]                                                                                           │
│     volumes: [postgres-data:/var/lib/postgresql/data]                                                              │
│     healthcheck:                                                                                                   │
│       test: ["CMD-SHELL", "pg_isready -U aiwriter"]                                                                │
│                                                                                                                    │
│   redis:                                                                                                           │
│     image: redis:8-alpine                                                                                          │
│     ports: ["6379:6379"]                                                                                           │
│     healthcheck:                                                                                                   │
│       test: ["CMD", "redis-cli", "ping"]                                                                           │
│                                                                                                                    │
│   backend:                                                                                                         │
│     bu ./backend                                                                                               │
│     ports: ["8000:8000"]                                                                                           │
│     depends_on:                                                                                                    │
│       postgres: { condition: service_healthy }                                                                     │
│       redis: { condition: service_healthy }                                                                        │
│     environment:                                                                                                   │
│       DATABASE_URL: postgresql+asyncpg://aiwriter:${DB_PASSWORD}@postgres/aiwriter                                 │
│       REDIS_URL: redis://redis:6379                                                                                │
│       CELERY_BROKER_URL: redis://redis:6379/1                                                                      │
│                                                                                                                    │
│   celery-worker:                                                                                                   │
│     build: ./backend                                                                                               │
│     command: celery -A app.jobs.celery_app worker -l info -c 4 -Q default,writing,audit                            │
│     depends_on: [postgres, redis]                                                                                  │
│                                                                                                                    │
│   celery-beat:                                                                                                     │
│     build: ./backend                                                                                               │
│     command: celery -A app.jobs.celery_app beat -l info                                                            │
│     depends_on: [redis]                                                                                            │
│                                                                                                                    │
│   flower:                                                                                                          │
│     image: mher/flower                                                                                             │
│     ports: ["5555:5555"]                                                                                           │
│     depends_on: [redis]                                                                                            │
│     environment:                                                                                                   │
│       CY_BROKER_URL: redis://redis:6379/1                                                                      │
│                                                                                                                    │
│   frontend:                                                                                                        │
│     build: ./frontend                                                                                              │
│     ports: ["3000:3000"]                                                                                           │
│     depends_on: [backend]                                                                                          │
│                                                                                                                    │
│ volumes:                                                                                                           │
│   postgres-data:                                                                                                   │
│                                                                                                                    │
│ 5.2 监控指标                                                                                                       │
│                                                                                                                    │
│ LLM 调用指标：                                                                                                   │
│ - 每分钟调用量 / 每模型 token 消耗 / 平均延迟 / 错误率                                                             │
│ - 告警：单次调用 > 60s / 错误率 > 5% / 单日成本超预算                                                              │
│                                                                                                                    │
│ 管线指标：                                                                                                         │
│ - Agent 执行耗时 / 审计通过率 / 修订轮次分布 / 去 AI 味通过率                                                      │
│ - 告警：单章生成 > 10min / 审计通过率 < 80%                                                                        │
│                                                                                                                    │
│ 系统指标：                                                                                               │
│ - CPU/内存/磁盘 / Celery 队列长度 / PostgreSQL 连接池利用率                                                        │
│ - 告警：队列积压 > 50 / 数据库连接 > 80%                                                                           │
│                                                                                                                    │
│ 业务指标（Dashboard 展示                                                                                       │
│ - 每日生成章节数 / 候选稿采纳率 / 人工干预率 / 伏笔回收率                                                          │
│                                                                                                                    │
│ 5.3 扩展策略                                                                                                       │
│                                                                                                              │
│ 水平扩展：                                                                                                         │
│ - Celery worker 按队列拆分（writing 队列 / audit 队列 / settler 队列）                                             │
│ - PostgreSQL read replica 分离读写                                                                                 │
│                                                                                                        │
│ 功能扩展点（插件化设计）：                                                                                         │
│ - 新模型：在 providers/ 添加适配器 + 在 ProviderType 枚举注册                                                      │
│ - 新 Agent：在 agents/ 添加 Agent 类 + 在 Pipeline DAG 配置中注册                                                  │
│ - 新题材：在files 目录添加 YAML 模板                                                                     │
│ - 新审计维度：在审计维度注册表添加 Check 类                                                                        │
│                                                                                                                    │
│ ---                                                                                                                │
│ 六、非功能性é                                                                                        │
│                                                                                                                    │
│ 6.1 性能指标                                                                                                       │
│                                                                                                                    │
│ ┌────────────â─────────────┬──────────┐                                                                        │
│ │             指标             │  目标值  │                                                                        │
│ ├──────────────────────────────┼──────────┤                                                                        │
│ │ 单章å < 5 分钟 │                                                                        │
│ ├──────────────────────────────┼──────────┤                                                                        │
│ │ 大纲生成（单节点）           │ < 30 秒  │                                                                        │
│ ├──────────────────────────────┼──────────┤                                                                        │
│ │ API CRUD 响应 (P99)          │ < 200ms  │                                                                        │
│ ├──────────────────────────────┼──────────┤                                                                        │
│ │ 混合 RAG 检索延迟        │ < 500ms  │                                                                        │
│ ├──────────────────────────────┼──────────┤                                                                        │
│ │ 并发 Agent 执行数            │ ≥ 4      │                                                                        │
│ ├────────────────────â─────┼──────────┤                                                                        │
│ │ 前端首屏加载                 │ < 2s     │                                                                        │
│ └──────────────────────────────┴──────────┘                                                                        │
│                                                                                                            │
│ 6.2 安全性                                                                                                         │
│                                                                                                                    │
│ - API 密钥加密存储（Fernet 对称加密）                                                                              │
│ - Pydantic v2 严格模式输入校验                                                                       │
│ - Prompt 注入防护（用户输入清洗后再注入 LLM prompt）                                                               │
│ - LLM 输出内容安全检查                                                                                             │
│ - CORS 白名单                                                                                                      │
│ - LLM 调用速率限制（防账单爆炸）                                                                                   │
│ - 全链路审计日志                                                                                                   │
│                                                                                                                    │
│ 6.3 可靠性                                                                                                         │
│                                                                                                                │
│ - LLM 重试：指数退避，最多 3 次（429 延长间隔，500 立即重试）                                                      │
│ - Provider fallback：主模型失败自动切换备用 Provider                                                               │
│ - 管线断点恢复：每个 Agent 节点完成后持久化中间状态，重启后可恢复                                                  │
│ - 候选稿，不覆盖正式稿                                                                    │
│ - 数据备份：PostgreSQL 定时 pg_dump + WAL 归档                                                                     │
│ - 优雅降级：RAG 不可用时回退到简单上下文组装                                                                       │
│                                                                                                                    │
│ ---                                                                                                      │
│ 七、实施路线图                                                                                                     │
│                                                                                                                    │
│ 迭代 1：项目骨架 + 数据层（2-3 周）                                                                                │
│                                                                                                            │
│ - 初始化全新项目结构（FastAPI backend + Next.js frontend）                                                         │
│ - Docker Compose 配置（pgvector/pg17 + Redis 8）                                                                   │
│ - 数据库 Schema：projects, volumes, chapters, drafts, entities, relationships, truth_files, truth_file_history,    │
│ scene_cards, hooks, pacing_metat_records, memory_entries                                                     │
│ - Alembic 数据库迁移管理                                                                                           │
│ - 基础 CRUD API（projects, volumes, chapters, entities）                                                           │
│ - LLM Provider 适配器基类 + OpenAI 兼容实现（支持中转 API）                                                        │
│ - 极简 Token 认证（环境å®）                                                                                  │
│                                                                                                                    │
│ 迭代 2：核心 Agent 管线（3-4 周）                                                                                  │
│                                                                                                                    │
│ - BaseAgent 基类（输入/输出 scrompt 模板、重试、日志）                                                      │
│ - Architect Agent：从创意生成 story_bible → volume_outline → chapters → scene_cards                                │
│ - Writer Agent Phase1：创意写作（temperature=0.7）                                                                 │
│ - Writer Agent Phase2：状态结算（temperature=0.3）                                                                 │
│ - Settler Agent：Obseer(事实提取) + Settler(真相文件更新) + 实体入库                                             │
│ - Pipeline DAG 执行器（拓扑排序、条件分支、循环）                                                                  │
│ - Celery 任务队列集成                                                                                              │
│ - 世界模型引擎基础版（jieba + pyahocorasick 实体匹配）                                                             - POV-aware 上下文过滤                                                                                             │
│                                                                                                                    │
│ 迭代 3：质量保障 + 网文特化（3-4 周）                                                                              │
│                                                                                                                    │
│ 体系：基础护栏(25条) + 网文题材 Profile(玄幻/仙侠/都市) + book_rules                                     │
│ - 黄金三章规则（内置到 Architect 的 Prompt）：                                                                     │
│   - 第1章：抛出核心冲突，禁止大段背景灌输                                                                          │
│   - 第2章：展示金手指/核心能力，让读者看到爽点预期                                                       │
│   - 第3章：明确短期目标，给读者追读理由                                                                            │
│ - Auditor Agent + 33 维度审计系统                                                                                  │
│ - Reviser Agent 五模式修订（polish/rewrite/rework/spot-fix/anti-detect）                                           │
│ - De-AI Engine 四层去 AI 味                                                                                    │
│ - Pacing Controller（Strand Weave 三线交织 + 爽点密度基准）                                                        │
│ - 爽点六大执行模式注入 Writer Prompt                                                                               │
│                                                                                                                    │
│ 迭代 4：RAG + 前端（3-4 周）                                                                           │
│                                                                                                                    │
│ - Hybrid RAG 引擎（pgvector 向量 + BM25 关键词 + 图谱结构 + RRF 融合）                                             │
│ - Reranker 精排集成（BGE-Reranker / Jina）                                                                         │
│ - 前端 Studio 页面（创作现场：章节列表 + 编辑器 + Agent 进度面æ                                              │
│ - 前端 Atlas 页面（世界图谱：ReactFlow 实体关系可视化）                                                            │
│ - 前端 Dashboard 页面（审计报告 + 节奏仪表盘 + 伏笔追踪 + 成本统计）                                               │
│ - WebSocket/SSE 实时进度推送                                                                                       │
│                                                                                                      │
│ 迭代 5：生产化加固（2 周）                                                                                         │
│                                                                                                                    │
│ - Provider fallback 机制（主模型失败自动切换备用）                                                                 │
│ - 管线断点恢复（Agent 中间状态持久å                                                              │
│ - 全自动模式端到端测试（从创意到完稿的完整流程）                                                                   │
│ - 半自动模式（人机协作中断点）                                                                                     │
│ - 结构化日志（structlog）                                                                                          │
│ - 用量统计与成本追è                                                                                     │
│ - 数据导出（txt/epub/markdown）                                                                                    │
│                                                                                                                    │
│ ---                                                                                                                │
│ 八、关键设计决策总结                                                                                               │
│                                                                                                                    │
│ ┌────────────┬────────────────────────────────────────────────────────────────┬────────────────────â
│ │   决策点   │                              选择                              │            理由             │      │
│ ├────────────┼────────────────────────────────────────────────────────────────┼─────────────────────────────┤      │
│ │ Agent 数量 │ 7 ä/Architect/Context/Writer/Settler/Auditor/Reviser） │ 职责单一、可独立测试和迭代  │      │
│ ├────────────┼────────────────────────────────────────────────────────────────┼─────────────────────────────┤      │
│ │ 状态管理   │ 10 个真相文件（数据库å¨）                                    │ 结构化、可审计、可版本回溯  │      │
│ ├────────────┼────────────────────────────────────────────────────────────────┼─────────────────────────────┤      │
│ │ RAG 方案   │ 三通道混合（向量+BM25+图谱）                                 │ 语义+精确+结构三维度覆盖    │      │
│ ├────────────┼────────────────────────────────────────────────────────────────┼─────────────────────────────┤      │
│ │ 审计维度   │ 33 维度 6 大类                                                 │ 全面覆盖，可按题材启用/禁用 │      │
│ ├────────────┼────────────────────────────────────────────────────────────────┼─────────────────────────────┤      │
│ │ 节奏系统   │ Strand Weave 三线交织                                          │ 网文场æ    │
│ ├────────────┼────────────────────────────────────────────────────────────────┼─────────────────────────────┤      │
│ │ 去 AI 味   │ 四层处理（预防+检测+修订+统计）                                │ 系统性方案而非零散修补      │      │
│──────────┼────────────────────────────────────────────────────────────────┼─────────────────────────────┤      │
│ │ 部署方案   │ Docker Compose（终态）                                         │ 个人自用无需 K8s            │      │
│ ├──────────â──────────────────────────────────────────────────────────┼─────────────────────────────┤      │
│ │ 认证方案   │ 环境变量 Token / 极简密码                                      │ 自用场景不需要复杂权限体系  │      │
│ ├────────────┼──────────────────────────────────────────────────────────┼─────────────────────────────┤      │
│ │ 人机协作   │ 候选稿 + 中断点 + 双模式                                       │ 全自动和半自动灵活切换      │      │
│ ├────────────┼─────────────────────â─────────────────────────────────────┼─────────────────────────────┤      │
│ │ 网文特化   │ 黄金三章 + 爽点密度 + 6种爽点模式                              │ 面向网文读者的阅读体验优化  │      │
│ └────────────┴─────────────────────────────â─────────────────────┴─────────────────────────────┘      │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────â─╯

