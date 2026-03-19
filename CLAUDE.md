# BioOpenClaw — Claude Code 项目指令

> **Version**: v0.3 | **Last Updated**: 2026-03-15
> **Status**: Phase 1 MVP（MCP 桥接验证阶段）

---

## 一、项目定位

BioOpenClaw 是**多 OpenClaw 实例的多 AI 生物信息科学家群框架**。五个 AI 实例（Scout、Data、Model、Research、Watcher）分工协作，完成从模型监控、数据获取、模型微调到文献研究的全链路生物信息科学工作。

**当前阶段 P0 目标**：MCP 桥接验证——确保 OpenClaw（Node.js）能够调用 Python 生信工具链。

---

## 二、五实例架构概览

| 实例 | 职责 | 主要工具 |
|------|------|---------|
| **Scout Agent** | 监控 HuggingFace/arXiv，维护模型注册表 | HuggingFace Hub API, arXiv API |
| **Data Agent** | GEO/TCGA 数据下载、Scanpy 质控、批次校正 | GEOparse, Scanpy, Harmony |
| **Model Agent** | LoRA/QLoRA 微调、Triton 推理服务 | PEFT, Triton, vLLM |
| **Research Agent** | 文献挖掘、假设生成、统计检验 | PubMed API, BioPython |
| **Watcher** | 全局监控、循环检测、纠偏注入 | 哈希对比, inbox 写入 |

---

## 三、三层记忆架构（v0.3）

### 设计原则（8条规则）

1. **身份指令与学习笔记分离**：SOUL.md（人类写）与 MEMORY.md（Agent 写）分开存储
2. **每个记忆文件必须可通过索引发现**：不存在孤儿文件
3. **每条学习记忆必须带日期戳**：格式 `[YYYY-MM-DD]`
4. **每个自动加载文件有大小上限**：MEMORY.md 硬上限 200 行
5. **按需加载优于全量加载**：通过 Topic Routing 表选择性加载
6. **单一写入者，固定 Schema**：每个文件的写入规则明确
7. **每个索引必须有陈旧检测**：定期运行 `memory_consistency_check.py`
8. **每个事实只存在于一个规范位置**：禁止跨文件重复信息

### 三层结构

- **Layer 1（Always Loaded）**：`SOUL.md` + `MEMORY.md`（200行上限）+ `shared_memory/_index.md`
- **Layer 2（Session Lifecycle）**：`active_context.md`（会话状态）+ `daily_log/YYYY-MM-DD.md`
- **Layer 3（On-Demand）**：`topics/`（领域知识）+ `shared_memory/`（跨实例）

---

## 四、目录结构

```
F:/xiehe_project/openclaw-bioinfor/
├── CLAUDE.md                           ← 本文件（项目指令，每次会话自动加载）
├── IMPLEMENTATION_PROMPTS.md           ← 11步实现提示词（按阶段排列）
├── agents/
│   ├── scout_agent/
│   │   ├── SOUL.md                     [L1] 身份边界（人类编写）
│   │   ├── MEMORY.md                   [L1] 核心经验（Agent写入，200行上限）
│   │   ├── active_context.md           [L2] 当前任务状态
│   │   ├── scout_core.py               Scout核心业务逻辑
│   │   ├── topics/
│   │   │   ├── huggingface_monitoring.md
│   │   │   └── benchmark_tracking.md
│   │   └── daily_log/
│   ├── data_agent/
│   │   ├── SOUL.md
│   │   ├── MEMORY.md
│   │   ├── active_context.md
│   │   ├── data_pipeline.py            Data核心业务逻辑
│   │   ├── topics/
│   │   │   ├── geo_download.md
│   │   │   ├── scanpy_qc.md
│   │   │   └── batch_correction.md
│   │   └── daily_log/
│   ├── model_agent/
│   │   ├── SOUL.md
│   │   ├── MEMORY.md
│   │   ├── active_context.md
│   │   ├── topics/
│   │   │   ├── lora_finetuning.md
│   │   │   └── triton_serving.md
│   │   └── daily_log/
│   ├── research_agent/
│   │   ├── SOUL.md
│   │   ├── MEMORY.md
│   │   ├── active_context.md
│   │   ├── topics/
│   │   │   ├── hypothesis_generation.md
│   │   │   └── statistical_testing.md
│   │   └── daily_log/
│   └── watcher/
│       ├── SOUL.md
│       ├── MEMORY.md
│       ├── active_context.md
│       ├── watcher_core.py             Watcher核心业务逻辑
│       ├── topics/
│       │   ├── loop_detection.md
│       │   └── steering_patterns.md
│       ├── corrections_log/
│       └── daily_log/
├── shared_memory/
│   ├── _index.md                       [L1] 共享知识路由表（每次加载）
│   ├── conventions.md                  [L1] 团队约定（人类编写）
│   ├── known_issues.md                 [L3] 已知问题
│   ├── model_registry/
│   │   ├── _index.md
│   │   ├── ESM2.md
│   │   ├── scGPT.md
│   │   ├── Geneformer.md
│   │   └── Evo2.md
│   ├── literature/
│   │   └── _index.md
│   ├── experiments/
│   │   └── _index.md
│   └── inbox/                          跨实例消息投递
├── scripts/
│   ├── memory_rotate.py                归档MEMORY.md超200行的旧条目
│   ├── memory_consistency_check.py     校验索引一致性
│   ├── daily_log_archive.py            归档14天前的日志
│   ├── memory_flush.py                 会话结束时同步记忆
│   ├── inbox_dispatch.py               扫描inbox分发消息
│   └── test_mcp_connection.py          MCP连接验证
└── mcp_server/
    └── server.py                       MCP Python服务器（P0核心）
```

---

## 五、编码约定

### 语言与版本
- **Python**: 3.10+，使用类型注解
- **Node.js**: 18+（OpenClaw框架）
- **格式化工具**: Black（Python），Prettier（JS）

### 记忆文件规范
- **日期戳格式**：`[YYYY-MM-DD]`（每条 Core Lesson 必须以此开头）
- **MEMORY.md Section**：仅允许 `## Topic Routing`、`## Core Lessons`、`## Active Warnings` 三个固定 section，禁止新增
- **active_context.md Section**：仅允许 `## Current Focus`、`## Blocked`、`## Next Steps`、`## Recent Decisions` 四个固定 section
- **写入者限制**：每个文件的写入者在 SOUL.md 中明确声明，严格遵守
- **inbox 消息格式**：YAML front matter（from/to/priority/created/type）+ Markdown body

### Git 提交约定
- Watcher 纠偏记录写入时，commit message 格式：`[watcher] correction: <agent> - <trigger_type>`
- 记忆文件更新：`[memory] <agent>: <operation>`
- 功能开发：`[feat] <component>: <description>`

### 文件命名约定
- daily_log 文件：`YYYY-MM-DD.md`
- 实验记录：`YYYY-MM-DD_<experiment_name>.md`
- inbox 消息：`YYYY-MM-DDTHH-MM-SS_<from>_to_<to>.md`

---

## 六、当前阶段（Phase 1 MVP）重点

### P0 任务（最高优先级）
**MCP 桥接验证**：确保 `mcp_server/server.py`（Python）的工具可被 OpenClaw（Node.js）调用

验证工具：
- `run_scanpy_qc` — Scanpy 质控流程
- `download_geo_data` — GEO 数据下载
- `query_huggingface` — HuggingFace 模型搜索
- `search_literature` — 文献搜索

验证脚本：`scripts/test_mcp_connection.py`

### P1 任务（本阶段完成）
- Scout + 记忆层原型：HuggingFace Hub 自动查询 + Markdown 记忆全流程
- 记忆一致性校验：`memory_consistency_check.py` 0错误

---

## 七、Phase 1 禁止事项

> 以下内容在 Phase 1 **严格禁止**，留待 Phase 2/3：

- **禁止**引入 Zep、Graphiti、Letta 等外部数据库服务
- **禁止**引入 Neo4j、向量数据库（Qdrant、Weaviate 等）
- **禁止**引入 ChromaDB（Phase 2 才引入）
- **禁止**在未经 Watcher 校验的情况下，让 Agent 直接修改其他 Agent 的记忆文件
- **禁止**创建超过 200 行的 MEMORY.md（超出时调用 `memory_rotate.py`）
- **禁止**在 shared_memory 中创建不在 `_index.md` 路由表里的孤儿文件

---

## 八、快速操作参考

### 记忆维护
```bash
# 检查记忆一致性（每日运行）
python scripts/memory_consistency_check.py

# 轮换超限的MEMORY.md（每周运行）
python scripts/memory_rotate.py

# 归档旧日志（每日运行）
python scripts/daily_log_archive.py

# 会话结束时同步
python scripts/memory_flush.py --agent <agent_name>
```

### MCP 服务器
```bash
# 启动 MCP Python 服务器
python mcp_server/server.py

# 测试 MCP 连接
python scripts/test_mcp_connection.py
```

### inbox 消息分发
```bash
# 扫描并分发 inbox 消息
python scripts/inbox_dispatch.py
```

---

## 九、关键文档引用

- **架构设计**：`BioOpenClaw_v0.2_优化设计文档_updated.docx`（五实例架构）
- **记忆系统**：`BioOpenClaw_v0.3_持久化记忆系统设计.md`（三层记忆，替代v0.2第六节）
- **实现提示词**：`IMPLEMENTATION_PROMPTS.md`（11步实现计划）

---

## 十、当前项目状态

```
Phase 1 MVP 进度：
[x] 目录结构初始化
[x] SOUL.md（5个Agent）
[x] MEMORY.md + active_context.md 模板
[x] shared_memory 索引体系
[x] 4个维护脚本
[x] MCP Python Server
[x] Scout Agent 核心逻辑
[x] Watcher 纠偏监控
[x] Data Agent 生信管道
[ ] 全流程集成测试（Step 11）
```

Last updated: 2026-03-15
