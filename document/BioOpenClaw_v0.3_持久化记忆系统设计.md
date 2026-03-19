# BioOpenClaw

## 多实例 AI 生物信息科学家群框架设计文档

**持久化记忆系统专项设计 v0.3** | 2026-03-15

状态：深化设计（替代 v0.2 第六节）

---

> 本文档是 BioOpenClaw v0.2 设计文档的**第六节（持久化记忆系统）**的完整替代方案。v0.2 提出的 Zep/Graphiti + Letta 方案经过行业调研后重新评估，改为以 Markdown 文件为主力的三层记忆架构。本文档同时更新了 v0.2 中涉及记忆系统的关联章节（4.4 纠偏记忆、9.1 验证计划 P1）。

---

## 一、变更摘要

| 变更项 | v0.2 方案 | v0.3 方案 | 变更理由 |
|--------|----------|----------|---------|
| 主记忆层 | Zep/Graphiti 时序知识图谱 | Markdown 文件 + Git 版本控制 | 与行业最佳实践对齐，零基础设施 |
| 实例内部状态 | Letta 分层记忆运行时 | `MEMORY.md` + `active_context.md` | 消除外部依赖，LLM 原生格式 |
| 纠偏记忆存储 | `.learnings/` + Zep/Graphiti | `corrections_log/` + `topics/steering_patterns.md` | 纯文件方案，人类可直接审计 |
| 记忆检索 | 混合检索（BM25 + 语义 + 图遍历） | 索引路由 + 文件系统检索（Phase 1）；ChromaDB 语义索引（Phase 2） | 小规模语料下文件检索优于向量 RAG |
| Zep/Graphiti 定位 | 起步方案 | Phase 3 演进方向 | 其价值场景（复杂关联查询）在早期不会出现 |

---

## 二、行业调研：主流 AI Agent 如何做持久记忆

### 2.1 调研范围

对 6 个主流 AI Agent 平台的持久记忆机制进行了系统调研。

### 2.2 各平台记忆架构

**Claude Code (Anthropic)**

Claude Code 采用双轨记忆系统，全部基于 Markdown 文件：

- `CLAUDE.md`：人类写给 Agent 的持久指令，涵盖项目架构、编码标准、工作流偏好。按目录层级加载（项目级、用户级、组织级），支持通过 `@path` 语法导入外部文件。
- `MEMORY.md`（Auto Memory）：Agent 自己积累的项目笔记，存储于 `~/.claude/projects/<project>/memory/`。前 200 行在每次会话自动加载，超出部分溢出到 topic 文件（如 `debugging.md`、`api-conventions.md`），按需读取。
- `.claude/rules/`：路径敏感规则，支持 YAML frontmatter 中的 `paths` 字段实现 glob 匹配，仅当 Agent 操作匹配文件时加载。
- 子 Agent 支持维护独立的 auto memory。

高级用户实践（Ian Paterson，34 个项目实战 22 天）验证了一套 4 层记忆架构：

| 层级 | 内容 | 加载方式 |
|------|------|---------|
| Always Loaded | MEMORY.md（200 行上限）+ CLAUDE.md | 每次会话自动注入 |
| Daily Logs | `daily-log/YYYY-MM-DD.md`，每次 flush 追加 | 加载当天和前一天 |
| Project State | CLAUDE.md 中的 `## State` 区段 | 随 CLAUDE.md 加载 |
| On-Demand | 10 个 topic 文件 + 22 个共享上下文文件 + 6 个导航索引 | 按域名映射表按需加载 |

配套自动化维护：
- `rotate-memory-lessons.sh`（每周）：归档 MEMORY.md 超 200 行的旧条目
- `check-memory-rules.sh`（每周）：校验 8 条设计规则的合规性
- `check-consistency.sh`（每日）：比对索引与磁盘文件的一致性
- `rotate-state-entries.sh`（每周）：归档超过两周的项目状态条目

关键指标：全部 50 个纯 Markdown 文件，Git 追踪，零基础设施成本。LlamaIndex 2026 年 1 月基准测试显示，在 100 个文档以下的语料库中，文件系统检索在正确性（8.4 vs 6.4）和相关性（9.6 vs 8.0）上均优于向量 RAG。

**Cursor IDE**

- `.cursor/rules/*.mdc` 文件，支持 YAML frontmatter 指定 `globs`（路径匹配）和 `alwaysApply`。
- 4 种激活模式：Always Apply / Apply Intelligently / Apply to Specific Files / Apply Manually。
- `AGENTS.md` 作为简化替代方案，放在项目根目录即可。
- 层级优先级：Team Rules > Project Rules > User Rules > AGENTS.md。
- 建议每个规则文件不超过 500 行。

**Windsurf/Cascade**

- `global_rules.md`（全局）+ `.windsurfrules` 或 `.windsurf/rules`（工作区级）。
- Agent 可自主生成和存储记忆（workspace-specific），自动按相关性检索注入上下文。
- 社区方案 Cascade Memory Bank 扩展了记忆目录结构：active context / product context / progress tracking / decision logs。

**Cline/Roo Code**

- Memory Bank 包含 6 个核心 Markdown 文件：
  - `projectbrief.md`（项目定义，变更最少）
  - `productContext.md`（产品上下文）
  - `activeContext.md`（当前工作焦点，变更最频繁）
  - `systemPatterns.md`（架构模式）
  - `techContext.md`（技术栈与约束）
  - `progress.md`（进度追踪）
- 显式区分短期记忆（activeContext, progress）与长期记忆（systemPatterns, techContext, projectbrief）。
- 初始化命令："initialize memory bank"，更新命令："update memory bank"。

**OpenHands**

- 事件持久化：`events/` 目录存储序列化事件文件 + `base_state.json` 核心状态。
- Context Condensation（2025 年 4 月引入）：智能压缩旧对话，保留用户目标、进展、技术细节，将每轮 API 成本降低最多 2 倍。
- `ConversationMemory` 类封装历史管理，确保事件配对和 LLM 兼容的消息转换。

### 2.3 跨平台共性设计模式

经过对比分析，提炼出 6 个跨平台一致的设计模式：

1. **身份指令与学习笔记分离**：人类写的规则（CLAUDE.md / .cursorrules / SOUL.md）与 Agent 自己积累的经验（MEMORY.md / auto memory）分开存储、分开加载、分别维护。
2. **大小上限 + 溢出机制**：Claude Code 对 MEMORY.md 设 200 行硬上限，超出溢出到 topic 文件；Cursor 建议每个规则文件不超过 500 行。目的是防止上下文窗口被记忆消耗殆尽。
3. **按需加载（Scoped Loading）**：不是所有记忆都在每次会话加载。Claude Code 按 topic 路由表加载，Cursor 按文件路径 glob 匹配加载，Cline 按记忆类型（短期/长期）区分加载频率。
4. **自动维护**：定期轮换过期记忆、检查索引一致性、归档旧条目。Claude Code 用 cron 脚本实现全自动维护。
5. **Git 版本控制**：所有平台推荐将记忆文件纳入版本管理。Git 天然提供时序追踪（commit 历史）、变更审计（diff）、分支隔离。
6. **纯文本格式**：6 个平台无一使用数据库作为主力记忆存储。Markdown 对 LLM 是原生格式——零序列化/反序列化开销，人类可直接阅读和编辑。

---

## 三、v0.2 方案（Zep/Graphiti + Letta）重新评估

### 3.1 技术可行性确认

v0.2 提出的方案在技术上是成熟的：

| 框架 | 架构特点 | 关键指标 |
|------|---------|---------|
| Zep/Graphiti | 时序知识图谱，双时间戳，混合检索（BM25 + 语义 + 图遍历） | DMR 94.8%，生产延迟 <200ms |
| Letta | LLM-as-OS 分层记忆：核心/回忆/归档，自主存取决策 | 21.2K★，Apache 2.0 |

### 3.2 与行业实践的偏差

尽管技术可行，该方案存在三个与行业最佳实践不一致的问题：

**问题一：基础设施复杂度与项目阶段不匹配**

BioOpenClaw Phase 1 的 P0 任务是 MCP 桥接验证（OpenClaw Node.js ↔ Python 生信工具），这是项目最大的工程风险。在此阶段引入 Zep（需要 Neo4j + 向量数据库 + 独立 API 服务）和 Letta（独立运行时）意味着：
- 需要部署和维护至少 3-4 个额外服务
- 调试链路变长：Agent 行为异常时需同时排查 LLM、MCP、Zep、Letta 多个环节
- 运维成本与项目当前阶段严重不匹配

**问题二：双系统边界模糊**

Zep 管理跨实例知识，Letta 管理单实例状态——这个边界在实践中会不断被挑战。例如：Watcher 纠偏 Data Agent 后形成的经验应存在 Zep（跨实例可查）还是 Data Agent 的 Letta（实例私有）？这类边界判断会在每个知识写入点反复出现。

**问题三：价值场景尚未出现**

Zep/Graphiti 相比文件系统的真正优势在于**复杂关联查询**——如"与 BRCA1 相关的所有模型在过去 6 个月的性能变化趋势"。这类查询需要图遍历和时序聚合能力，是 Markdown 文件难以实现的。但这是 Phase 3（生产规模运行后）才会频繁出现的需求，不应过早引入。

### 3.3 结论

Zep/Graphiti 是正确的**长期演进方向**，保留在技术路线图的 Phase 3。Phase 1 应以 Markdown 记忆系统起步——这与 Claude Code、Cursor、Windsurf、Cline、OpenHands 的实践完全一致。

---

## 四、BioOpenClaw 持久化记忆系统设计

### 4.1 设计原则

从 Claude Code 的 8 条记忆规则和 6 个平台的共性实践中提炼出以下设计原则：

| # | 原则 | 来源 | 说明 |
|---|------|------|------|
| 1 | 身份指令与学习笔记分离 | Claude Code, Cursor, 全平台 | SOUL.md 是人类定义的身份边界，MEMORY.md 是 Agent 自己积累的经验。两者分开存储、分开维护。 |
| 2 | 每个记忆文件必须可通过索引发现 | Claude Code Rule #1 | 不存在"孤儿文件"。所有文件必须被某个索引或路由表引用，否则对系统不可见。 |
| 3 | 每条学习记忆必须带日期戳 | Claude Code Rule #2 | 格式 `[YYYY-MM-DD]`。用于轮换排序和模式检测——同一教训出现 3+ 次说明是结构性问题，应提升到永久知识。 |
| 4 | 每个自动加载文件有大小上限 | Claude Code 200 行上限 | MEMORY.md 硬上限 200 行。超出部分溢出到 topic 文件。防止上下文窗口被记忆消耗殆尽。 |
| 5 | 按需加载优于全量加载 | Cursor path-specific rules, Claude Code topic routing | 不是所有知识都在每次会话加载。通过路由表和任务相关性选择性加载，节约上下文空间。 |
| 6 | 单一写入者，固定 Schema | Claude Code Rule #3, #6 | 每个记忆文件的写入规则明确（谁可以写、section header 有哪些），禁止创建随意的新 section。 |
| 7 | 每个索引必须有陈旧检测 | Claude Code Rule #5 | 定期校验索引与实际文件的一致性。索引漂移会导致 Agent 重建已有知识或忽略已有信息。 |
| 8 | 每个事实只存在于一个规范位置 | Claude Code Rule #6 | 禁止跨文件重复同一信息。信息重复必然导致不同步，不同步导致 Agent 行为不一致。 |

### 4.2 三层记忆架构

```
┌───────────────────────────────────────────────────────────────────────┐
│                 Layer 1: Always Loaded — 身份与核心记忆                │
│                                                                       │
│  ┌─────────────┐    ┌─────────────────┐    ┌────────────────────┐    │
│  │  SOUL.md    │    │   MEMORY.md     │    │ shared/_index.md   │    │
│  │ (人类编写)   │    │ (Agent 自动写入) │    │ (共享知识路由表)    │    │
│  │ 身份与边界   │    │ 200 行硬上限     │    │ 每次会话加载       │    │
│  └─────────────┘    └─────────────────┘    └────────────────────┘    │
│                                                                       │
│  加载时机：每次会话启动时自动注入上下文                                    │
├───────────────────────────────────────────────────────────────────────┤
│                 Layer 2: Session Lifecycle — 会话生命周期               │
│                                                                       │
│  ┌──────────────────────┐    ┌──────────────────────────────┐        │
│  │  active_context.md   │    │  daily_log/YYYY-MM-DD.md     │        │
│  │  当前任务状态          │    │  每日工作日志 (append-only)    │        │
│  │  会话开始读取/结束更新  │    │  每次 flush 追加条目          │        │
│  └──────────────────────┘    └──────────────────────────────┘        │
│                                                                       │
│  加载时机：会话启动时读取 active_context；daily_log 加载当天 + 前一天    │
├───────────────────────────────────────────────────────────────────────┤
│                 Layer 3: On-Demand — 按需加载知识库                     │
│                                                                       │
│  ┌────────────┐  ┌────────────────┐  ┌──────────┐  ┌─────────────┐  │
│  │ topics/    │  │ model_registry/│  │literature/│  │ experiments/│  │
│  │ 领域专项   │  │ 模型注册表      │  │ 文献知识  │  │ 实验记录    │  │
│  └────────────┘  └────────────────┘  └──────────┘  └─────────────┘  │
│                                                                       │
│  加载时机：仅当任务需要时，通过 MEMORY.md 的 Topic Routing 表定位后加载  │
└───────────────────────────────────────────────────────────────────────┘
```

### 4.3 目录结构

```
BioOpenClaw/
├── agents/
│   ├── data_agent/
│   │   ├── SOUL.md                      # [L1] 身份边界（人类编写，每次加载）
│   │   ├── MEMORY.md                    # [L1] 核心经验索引（Agent 写入，200 行上限，每次加载）
│   │   ├── active_context.md            # [L2] 当前任务焦点（会话间传递状态）
│   │   ├── topics/                      # [L3] MEMORY.md 溢出的领域知识（按需加载）
│   │   │   ├── geo_download.md          #      GEO 数据下载经验
│   │   │   ├── scanpy_qc.md             #      Scanpy 质控经验
│   │   │   └── batch_correction.md      #      批次校正经验
│   │   └── daily_log/                   # [L2] 每日工作日志
│   │       └── YYYY-MM-DD.md
│   │
│   ├── model_agent/
│   │   ├── SOUL.md
│   │   ├── MEMORY.md
│   │   ├── active_context.md
│   │   ├── topics/
│   │   │   ├── lora_finetuning.md       #      LoRA/QLoRA 微调经验
│   │   │   └── triton_serving.md        #      Triton 推理服务经验
│   │   └── daily_log/
│   │
│   ├── research_agent/
│   │   ├── SOUL.md
│   │   ├── MEMORY.md
│   │   ├── active_context.md
│   │   ├── topics/
│   │   │   ├── hypothesis_generation.md #      假设生成方法论
│   │   │   └── statistical_testing.md   #      统计检验经验
│   │   └── daily_log/
│   │
│   ├── scout_agent/
│   │   ├── SOUL.md
│   │   ├── MEMORY.md
│   │   ├── active_context.md
│   │   ├── topics/
│   │   │   ├── huggingface_monitoring.md#      HuggingFace 监控经验
│   │   │   └── benchmark_tracking.md    #      基准测试追踪经验
│   │   └── daily_log/
│   │
│   └── watcher/
│       ├── SOUL.md
│       ├── MEMORY.md
│       ├── active_context.md
│       ├── topics/
│       │   ├── loop_detection.md         #      循环检测模式库
│       │   └── steering_patterns.md      #      纠偏策略库
│       ├── corrections_log/              #      纠偏历史（append-only）
│       │   └── YYYY-MM-DD.md
│       └── daily_log/
│
├── shared_memory/                        # 跨实例共享知识
│   ├── _index.md                         # [L1] 共享知识总索引（路由表，每次加载）
│   ├── model_registry/                   # [L3] 模型注册表（Scout 写入，全员可读）
│   │   ├── _index.md                     #      模型汇总索引
│   │   ├── ESM2.md
│   │   ├── scGPT.md
│   │   ├── Geneformer.md
│   │   └── Evo2.md
│   ├── literature/                       # [L3] 文献知识库（Research Agent 写入）
│   │   ├── _index.md
│   │   └── <topic>.md
│   ├── experiments/                      # [L3] 实验记录（全员可写）
│   │   ├── _index.md
│   │   └── YYYY-MM-DD_<name>.md
│   ├── conventions.md                    # [L1] 团队约定（人类编写）
│   ├── known_issues.md                   # [L3] 已知问题（全员可追加）
│   └── inbox/                            # 跨实例消息投递（Agent 写入，调度脚本分发）
│
└── scripts/
    ├── memory_rotate.py                  # 定期轮换：归档 MEMORY.md 超 200 行的条目
    ├── memory_consistency_check.py       # 一致性校验：索引 vs 实际文件
    ├── daily_log_archive.py              # 归档 14 天前的日志
    └── memory_flush.py                   # 会话结束时调用：更新 active_context + 追加日志
```

### 4.4 Layer 1 详细设计：Always Loaded

每个 Agent 启动时加载三类文件，直接注入上下文。

#### SOUL.md（沿用 v0.2 设计）

人类编写的身份边界文件，定义 Agent 的职责范围、行为约束和协作规则。内容参见 v0.2 各实例的 SOUL.md 行为边界部分（3.5、4.5、5.5 节），此处不重复。

#### MEMORY.md

Agent 自动积累的核心经验文件。200 行硬上限，超出部分通过 Topic Routing 表指向 topic 文件。

**文件规范：**
- 写入者：仅限本 Agent 自身
- 格式：3 个固定 section header（Topic Routing / Core Lessons / Active Warnings），禁止创建新 section
- 日期戳：每条 lesson 必须以 `[YYYY-MM-DD]` 开头
- 排序：Core Lessons 按日期降序排列（最新在前）
- 上限：总行数不超过 200 行。超过时由 `memory_rotate.py` 自动将最旧条目归档到对应 topic 文件

**Data Agent MEMORY.md 示例：**

```markdown
# Data Agent Memory

## Topic Routing
- GEO 下载 -> topics/geo_download.md
- Scanpy 质控 -> topics/scanpy_qc.md
- 批次校正 -> topics/batch_correction.md

## Core Lessons
- [2026-03-15] TCGA bulk RNA-seq 数据在合并前必须检查 FPKM vs TPM 单位
- [2026-03-14] CellxGene Census TileDB 查询超时时，缩小 obs_filter 范围而非增加 timeout
- [2026-03-13] lakeFS 分支合并冲突时优先保留有完整 QC 报告的版本
- [2026-03-10] GEO 系列矩阵文件如果是 log2 转换过的，不要再做 log1p

## Active Warnings
- NCBI API 在 UTC 05:00-06:00 维护窗口期间频繁超时
- GEO 下载 > 5GB 时使用 Aspera 而非 FTP
```

#### shared_memory/_index.md

跨实例共享知识的路由表，所有 Agent 在会话启动时加载。

**文件规范：**
- 写入者：`memory_consistency_check.py` 自动维护，人类可手动编辑
- 功能：列出 shared_memory 下所有子目录及其主写者权限

**示例：**

```markdown
# BioOpenClaw Shared Memory Index

## Directory Routing

| 目录 | 内容 | 主写者 | 其他权限 |
|------|------|--------|---------|
| model_registry/ | 生物信息模型注册表 | Scout Agent | 全员只读 |
| literature/ | 文献知识库 | Research Agent | 全员只读 |
| experiments/ | 实验记录 | 全员 | 全员可追加 |
| inbox/ | 跨实例消息投递 | 全员 | 调度脚本分发 |

## Quick Links
- 模型总数: 4 (详见 model_registry/_index.md)
- 文献主题数: 1 (详见 literature/_index.md)
- 实验记录数: 0 (详见 experiments/_index.md)
- 已知问题: known_issues.md
- 团队约定: conventions.md

Last updated: 2026-03-15
```

### 4.5 Layer 2 详细设计：Session Lifecycle

#### active_context.md

记录"正在做什么、卡在哪里、下一步是什么"。每次会话开始时读取以恢复状态，会话结束时更新。

**文件规范：**
- 写入者：仅限本 Agent 自身（通过 `memory_flush.py` 调用）
- 格式：YAML front matter（last_session 时间戳）+ 4 个固定 section
- 更新频率：每次会话结束时整体覆盖更新（不是追加）

**Data Agent active_context.md 示例：**

```markdown
---
last_session: 2026-03-15T14:30:00
---

# Active Context

## Current Focus
- 正在处理 TCGA BRCA1 突变样本的单细胞数据，已完成质控，待批次校正

## Blocked
- GEO 数据集 GSE123456 下载失败（NCBI 限流），已排队重试

## Next Steps
1. 完成批次校正后通知 Model Agent 数据就绪
2. 等待 Scout Agent 确认最新 scGPT 版本

## Recent Decisions
- [2026-03-15] 选择 Harmony 而非 scVI 做批次校正：数据集只有 3 个批次，Harmony 足够
- [2026-03-14] TCGA 数据选用 Level 3 而非 Level 1：下游分析不需要原始测序读数
```

#### daily_log/YYYY-MM-DD.md

每日工作日志，append-only。每次 flush 追加一个时间戳条目。

**文件规范：**
- 写入者：仅限本 Agent 自身
- 格式：每个条目以 `HH:MM` 时间戳开头
- 保留策略：14 天内的日志保留在 `daily_log/`，更早的由 `daily_log_archive.py` 移至 `daily_log/archive/`

**示例：**

```markdown
# Data Agent Daily Log — 2026-03-15

14:30 - TCGA BRCA1 单细胞数据质控 (~45m)
**Done:**
- 完成 3 个批次的质控过滤（min_genes=200, min_cells=3, mt_pct<20%）
- 过滤后细胞数：Batch1: 8,234 / Batch2: 6,891 / Batch3: 7,456
**Blocked:** GSE123456 下载失败，NCBI 限流
**Decisions:** 选择 Harmony 做批次校正
**Lessons:** TCGA bulk 数据合并前必须检查 FPKM vs TPM 单位

10:00 - GEO 数据下载 (~30m)
**Done:**
- 成功下载 GSE789012（scRNA-seq, 10x Chromium, ~2.1GB）
- 验证 checksum 通过
**Lessons:** GEO 系列矩阵文件可能是 log2 转换过的，不要重复 log1p
```

### 4.6 Layer 3 详细设计：On-Demand Knowledge

仅在任务需要时加载。通过 MEMORY.md 的 Topic Routing 表定位对应文件。

#### Agent Topic 文件

MEMORY.md 超出 200 行时，最旧的 Core Lessons 按领域归档到对应 topic 文件中。

**Data Agent topics/geo_download.md 示例：**

```markdown
# GEO 数据下载经验

## 工具与 API
- 优先使用 GEOparse 库，比直接调用 FTP 更稳定
- 大文件（>5GB）使用 Aspera 协议
- NCBI API 需设置 ENTREZ_EMAIL 环境变量，否则限流严重

## 已知陷阱
- [2026-03-10] GEO 系列矩阵文件可能是 log2 转换过的，不要重复 log1p
- [2026-03-08] 部分 GSE 的 supplementary files 链接过期，需 fallback 到 SRA
- [2026-03-05] GEO 的 GPL 平台注释版本可能与实际数据不一致，必须交叉验证

## 速查表
| 数据类型 | 推荐下载方式 | 备注 |
|---------|------------|------|
| 系列矩阵 | GEOparse | 自动解析元数据 |
| 原始 FASTQ | SRA Toolkit prefetch + fasterq-dump | 比直接 FTP 快 3-5x |
| 补充文件 | wget / Aspera | 注意检查 checksum |
```

#### 共享模型注册表条目

`shared_memory/model_registry/` 中每个模型一个文件，由 Scout Agent 写入。

**文件规范：**
- 写入者：仅限 Scout Agent
- 格式：YAML front matter（结构化元数据）+ Markdown body（详细信息）
- 索引：变更后必须同步更新 `model_registry/_index.md`

**shared_memory/model_registry/scGPT.md 示例：**

```markdown
---
name: scGPT
version: "2.0"
updated: 2026-03-10
source: https://huggingface.co/bowang-lab/scGPT
paper: https://doi.org/10.1038/s41592-024-02201-0
license: MIT
parameters: 51.3M
architecture: Transformer
modalities: [scRNA-seq, spatial, CITE-seq]
species: [human, mouse]
---

# scGPT

## Benchmarks
- [2026-03] scIB batch integration: 0.82
- [2026-03] Cell type annotation (Immune Human): F1=0.94
- [2026-02] Gene perturbation prediction: Pearson r=0.71

## Known Limitations
- 对稀有细胞类型（<1% 占比）的标注准确率显著下降
- Spatial 模态需要 >=300 genes/spot
- 跨物种迁移（human -> mouse）性能下降 ~15%

## Fine-tuning Notes
- 推荐 LoRA rank=8, alpha=16, 学习率 2e-4
- 全参数微调需要 >= 24GB VRAM（A100 推荐）
- Flash Attention 2 可将训练速度提升 ~40%

## BioOpenClaw Usage History
- [2026-03-15] Data Agent: BRCA1 数据上 LoRA 微调, cell annotation F1=0.91
- [2026-03-12] Research Agent: 用于 KRAS 扰动预测, Pearson r=0.68
```

**shared_memory/model_registry/_index.md 示例：**

```markdown
# Model Registry Index

## Registered Models

| 模型 | 版本 | 类型 | 参数量 | 许可证 | 更新日期 | 详情 |
|------|------|------|-------|--------|---------|------|
| ESM2 | 3B/650M/150M/35M | 蛋白质语言模型 | 35M-3B | MIT | 2026-03-12 | ESM2.md |
| scGPT | 2.0 | 单细胞基础模型 | 51.3M | MIT | 2026-03-10 | scGPT.md |
| Geneformer | 1.0 | 单细胞基础模型 | 10M | CC-BY-NC | 2026-03-08 | Geneformer.md |
| Evo2 | 1.0 | DNA 基础模型 | 7B/40B | Apache 2.0 | 2026-03-05 | Evo2.md |

## Statistics
- Total models: 4
- Last scan: 2026-03-15
- Next scheduled scan: 2026-03-16

## Coverage Gaps
- 蛋白质结构预测模型（OpenFold3 等）尚未注册
- 药物分子生成模型（REINVENT4 等）尚未注册
```

#### Watcher 纠偏记录

`watcher/corrections_log/` 记录每一次纠偏操作，作为 Watcher 自我优化的数据来源。

**文件规范：**
- 写入者：仅限 Watcher
- 格式：每条纠偏记录包含时间戳、目标 Agent、触发条件、纠偏措施、效果评估
- 保留策略：与 daily_log 相同（14 天活跃，之后归档）

**watcher/corrections_log/2026-03-15.md 示例：**

```markdown
# Watcher Corrections Log — 2026-03-15

## 14:25 — Data Agent 循环检测
- **触发条件**: 连续 3 次相同 BLAST 查询（参数哈希一致），触发层级 1 硬规则
- **纠偏措施**: 注入 steering 消息："你已经重复执行相同的 BLAST 查询 3 次。请检查查询序列是否正确，或尝试调整 E-value 阈值。"
- **效果**: Data Agent 修改了 E-value 从 1e-5 到 1e-3，成功获得新结果
- **领域标签**: data_processing, blast
- **优先级**: medium

## 10:15 — Research Agent 进展停滞
- **触发条件**: 连续 5 轮输出 embedding 相似度 > 0.95，触发层级 2 软规则
- **纠偏措施**: 注入 steering 消息："你的最近 5 次输出高度相似，可能陷入原地踏步。建议换一个角度重新审视假设，或查阅 literature/ 中的最新文献。"
- **效果**: Research Agent 转向查阅新文献后提出了不同的假设方向
- **领域标签**: research, hypothesis
- **优先级**: high
```

### 4.7 记忆生命周期管理

```
会话启动
    │
    ▼
┌─────────────────────────────────────────┐
│ 自动加载 Layer 1:                        │
│   SOUL.md + MEMORY.md + shared/_index.md│
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│ 读取 Layer 2:                            │
│   active_context.md (恢复上次状态)        │
│   daily_log/今天.md + 昨天.md            │
└──────────────────┬──────────────────────┘
                   │
                   ▼
            ┌──────────────┐
            │   执行任务    │◄──────────────────────────┐
            └──────┬───────┘                            │
                   │                                    │
          ┌────────┴────────┐                           │
          │ 需要领域知识？    │── 是 ──► 通过 MEMORY.md  │
          └────────┬────────┘         Topic Routing     │
                   │                  加载 Layer 3 文件  │
                   │ 否                     │           │
                   ▼                        └───────────┘
            ┌──────────────┐
            │ 会话结束 /    │
            │ flush 触发    │
            └──────┬───────┘
                   │
        ┌──────────┼──────────────┐
        ▼          ▼              ▼
   更新          追加           追加
active_context  daily_log     MEMORY.md
   .md         今天.md       (如有新教训)
                                  │
                           ┌──────┴──────┐
                           │ > 200 行？   │
                           └──────┬──────┘
                                  │ 是
                                  ▼
                        溢出到对应 topic 文件
                       (由 memory_rotate.py 执行)
```

### 4.8 跨实例记忆共享机制

多 Agent 共享知识通过 `shared_memory/` 目录实现：

**写者权限模型：**

| 目录 | 主写者 | 读取权限 | 说明 |
|------|--------|---------|------|
| model_registry/ | Scout Agent | 全员 | 模型注册表 |
| literature/ | Research Agent | 全员 | 文献知识库 |
| experiments/ | 全员 | 全员 | 实验记录（各 Agent 可追加自己的实验结果） |
| inbox/ | 全员 | 调度脚本 | 跨实例消息投递（下文详述） |
| conventions.md | 人类 | 全员 | 团队约定 |
| known_issues.md | 全员 | 全员 | 已知问题（任何 Agent 发现问题都可追加） |

**inbox 跨实例通信机制：**

当一个 Agent 需要向另一个 Agent 传递知识（例如 Data Agent 发现某个模型在特定数据集上的问题，需要通知 Scout Agent 更新模型注册表），它将消息写入 `shared_memory/inbox/`：

```markdown
---
from: data_agent
to: scout_agent
priority: medium
created: 2026-03-15T14:30:00
type: model_issue
---

# 模型问题报告：scGPT 在 BRCA1 数据上的异常

scGPT v2.0 在 BRCA1 突变样本的 rare cell type annotation 上表现异常差（F1 < 0.3），
建议在 model_registry/scGPT.md 的 Known Limitations 中补充此信息。

相关数据：experiments/2026-03-15_BRCA1_scRNA.md
```

指挥层的调度脚本定期扫描 inbox 目录，根据 `to` 字段将消息分发到目标 Agent 的 active_context.md 的 Incoming Messages 区段（或直接路由到对应的 shared_memory 文件）。

### 4.9 维护脚本设计

| 脚本 | 运行频率 | 功能 |
|------|---------|------|
| `memory_rotate.py` | 每周 | 扫描所有 Agent 的 MEMORY.md，将超过 200 行的最旧条目归档到对应 topic 文件。归档时生成条目摘要，写入 topic 文件尾部。 |
| `memory_consistency_check.py` | 每日 | 1) 比对各 _index.md 与实际文件是否一致（检测孤儿文件和幽灵索引）；2) 检查所有 MEMORY.md 是否超过 200 行上限；3) 检查所有 Core Lessons 是否带日期戳；4) 输出校验报告。 |
| `daily_log_archive.py` | 每日 | 将 14 天前的 daily_log 文件移至 `daily_log/archive/`。Watcher 的 corrections_log 同理。 |
| `memory_flush.py` | 每次会话结束 | 1) 更新目标 Agent 的 active_context.md；2) 追加今日 daily_log 条目；3) 如有新教训，追加到 MEMORY.md 的 Core Lessons。 |

---

## 五、对 v0.2 关联章节的更新

### 5.1 更新：4.4 纠偏记忆与自我优化

**v0.2 原文（替代）：**
> 这些记忆通过 Zep/Graphiti 时序知识图谱存储，每条记忆带有双时间戳（valid_at / invalid_at），能跟踪经验的演化。

**v0.3 替代方案：**

纠偏记忆以 Markdown 文件存储在 `watcher/corrections_log/YYYY-MM-DD.md`（详见 4.6 节）。时序追踪通过 Git commit 历史实现，每次纠偏记录的写入对应一次 Git commit，commit message 包含 `[watcher] correction: <agent> - <trigger_type>`。

高频出现的纠偏模式（同一触发条件出现 3+ 次）由 `memory_rotate.py` 自动提升到 `watcher/topics/steering_patterns.md`，形成永久策略库。

关键警告保持不变：智能体具有"经验跟随"特性——错误的记忆会复合放大错误。在 Markdown 方案下，记忆的可审计性更强（人类可直接阅读 corrections_log），但仍需在 `memory_flush.py` 中实现选择性记忆添加逻辑（仅写入效果评估为正面的纠偏经验）。

### 5.2 更新：9.1 验证优先级 P1

**v0.2 原文（替代）：**
> P1 — Scout + 记忆层原型：HuggingFace Hub 自动查询 + Zep/Graphiti 存储全流程。验证时序图谱在模型注册表场景下的可用性。

**v0.3 替代方案：**

P1 — Scout + 记忆层原型：HuggingFace Hub 自动查询 + Markdown 记忆系统全流程。验证步骤：
1. Scout Agent 通过 HuggingFace Hub API 发现新模型
2. 自动生成 `shared_memory/model_registry/<model>.md` 文件（含 YAML front matter 和 Markdown body）
3. 自动更新 `shared_memory/model_registry/_index.md` 索引
4. 运行 `memory_consistency_check.py` 验证索引一致性

**成功标准（更新）：**
- P1：Scout 能自动发现上周新发布的生物基础模型，写入 model_registry Markdown 文件，并通过一致性校验

### 5.3 更新：技术选型快速参考

| 层次 | 组件 | v0.2 方案 | v0.3 方案 | 状态 |
|------|------|----------|----------|------|
| 记忆层 | 时序知识图谱 | Zep/Graphiti + Letta | Markdown 文件 + Git | [变更] Phase 1-2 |
| 记忆层 | 语义检索加速 | （包含在 Zep 中） | ChromaDB 本地模式 | [新增] Phase 2 |
| 记忆层 | 复杂关联查询 | （包含在 Zep 中） | Graphiti（渐进引入） | [保留] Phase 3 |
| 记忆维护 | 自动化维护 | （无） | Python cron 脚本 | [新增] Phase 1 |

---

## 六、渐进式演进路线

### Phase 1（当前 → MVP）

纯 Markdown + Git。零基础设施开销，快速验证。

- 完整实现 4.3 节的目录结构
- 为每个 Agent 编写 SOUL.md（身份边界）
- 实现 MEMORY.md、active_context.md、daily_log 的读写机制
- 实现 shared_memory 的写者权限控制和 inbox 消息分发
- 实现 4 个维护脚本
- 所有文件纳入 Git 版本管理

**知识检索方式**：MEMORY.md 的 Topic Routing 表 + 文件系统路径。在 50-100 个 MD 文件规模下，这种方式的检索质量优于向量 RAG（依据 LlamaIndex 2026.01 基准测试）。

### Phase 2（知识规模增长后）

在 Markdown 基础上叠加轻量语义检索层。

- 对 `shared_memory/model_registry/` 和 `shared_memory/literature/` 中的 MD 文件建立 ChromaDB 本地嵌入索引
- Agent 可通过语义查询检索相关模型或文献（如"擅长 batch correction 的单细胞模型"）
- MD 文件仍然是唯一真实来源，ChromaDB 只是检索加速层
- 增量索引：新文件写入时自动更新嵌入

**触发条件**：model_registry 超过 50 个条目，或 literature 超过 100 个文件。

### Phase 3（需要复杂关联查询时）

引入 Graphiti 时序知识图谱。

- 将 MD 文件内容定期同步到 Graphiti 图谱
- MD 仍保留为人类可审计的真实来源（single source of truth）
- Graphiti 专门用于回答跨实体、跨时序的关联查询（如"BRCA1 相关模型在过去 6 个月的性能演化趋势"、"哪些数据集同时被 Model Agent 和 Research Agent 使用过"）
- 写入路径：Agent → MD 文件 → 同步脚本 → Graphiti

**触发条件**：跨实例关联查询成为频繁需求，且文件系统检索无法高效满足。

---

## 七、与 v0.2 其他章节的兼容性

本 v0.3 方案仅替代 v0.2 的第六节（持久化记忆系统），并更新了关联的 4.4 节和 9.1 节 P1。以下章节**完全保持不变**：

- 一、框架概述与核心理念
- 二、系统架构（v0.2）
- 三、Scout OpenClaw（3.1-3.5）
- 四、Watcher OpenClaw（4.1-4.3，4.5）— 仅 4.4 纠偏记忆部分更新
- 五、Data OpenClaw 四层数据架构（5.1-5.5）
- 七、参考系统调研
- 八、技术选型快速参考 — 记忆层行更新（见 5.3 节）
- 九、Phase 1 验证计划 — P1 更新（见 5.2 节），P0/P2/P3 不变

---

文档持续更新中。下一步：实现 Phase 1 的目录结构、模板文件和维护脚本。
