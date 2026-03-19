# BioOpenClaw 团队约定

> **写入者**: 人类（项目维护者）| **禁止 Agent 修改本文件**
> **加载时机**: Layer 1 — 每次会话启动时加载
> **版本**: v0.3 | **最后更新**: 2026-03-15

---

## 一、记忆文件规范

### 通用规则

1. **日期戳格式**：`[YYYY-MM-DD]`（每条 Core Lesson 必须以此开头）
2. **文件大小上限**：MEMORY.md 硬上限 200 行，超出调用 `memory_rotate.py` 归档
3. **单一写入者**：每个文件只有一个被授权的写入者，不得跨越写入
4. **每个事实只存在于一个位置**：禁止跨文件重复同一信息
5. **孤儿文件零容忍**：所有文件必须被某个 `_index.md` 引用

### MEMORY.md 固定 Schema

仅允许三个 section header（**禁止**新增或修改 section 名称）：
```markdown
## Topic Routing
## Core Lessons
## Active Warnings
```

### active_context.md 固定 Schema

仅允许四个 section header：
```markdown
## Current Focus
## Blocked
## Next Steps
## Recent Decisions
## Incoming Messages
```

---

## 二、文件命名约定

| 文件类型 | 命名格式 | 示例 |
|---------|---------|------|
| daily_log | `YYYY-MM-DD.md` | `2026-03-15.md` |
| 实验记录 | `YYYY-MM-DD_<name>.md` | `2026-03-15_BRCA1_scRNA.md` |
| corrections_log | `YYYY-MM-DD.md` | `2026-03-15.md` |
| inbox 消息 | `YYYY-MM-DDTHH-MM-SS_<from>_to_<to>.md` | `2026-03-15T14-30-00_data_to_scout.md` |
| 模型注册表 | `<ModelName>.md` | `scGPT.md`, `ESM2.md` |
| topic 文件 | `<topic_name>.md`（下划线分隔） | `geo_download.md` |

---

## 三、Git Commit 约定

| 类型 | 格式 | 示例 |
|------|------|------|
| Watcher 纠偏 | `[watcher] correction: <agent> - <trigger_type>` | `[watcher] correction: data_agent - loop_detection` |
| 记忆更新 | `[memory] <agent>: <operation>` | `[memory] scout: add ESM3 to registry` |
| 功能开发 | `[feat] <component>: <description>` | `[feat] mcp: add run_scanpy_qc tool` |
| 修复 | `[fix] <component>: <description>` | `[fix] memory_rotate: handle empty topic file` |
| 文档 | `[docs] <file>: <description>` | `[docs] SOUL.md: update cooperation rules` |

---

## 四、Python 编码约定

- **版本**: Python 3.10+
- **类型注解**: 所有函数必须有类型注解（参数和返回值）
- **格式化**: Black（行宽 100）
- **导入顺序**: stdlib → third-party → local（按 isort 标准）
- **错误处理**: 在系统边界（外部 API、文件 I/O）使用 try/except，内部逻辑不过度防御
- **日志**: 使用 `logging` 模块，不使用 `print`（生产代码）

---

## 五、环境变量约定

以下环境变量需要在运行前设置：

| 变量 | 用途 | 必填 |
|------|------|------|
| `HF_TOKEN` | HuggingFace Hub API 认证（提升速率限制）| 推荐 |
| `ENTREZ_EMAIL` | NCBI Entrez API（PubMed、GEO）| **必填** |
| `NCBI_API_KEY` | NCBI API 速率提升 | 推荐 |

---

## 六、Phase 1 禁止事项

> 以下内容在 Phase 1 **严格禁止**：

- Zep、Graphiti、Letta 等外部数据库服务
- Neo4j、任何向量数据库（Qdrant、Weaviate、Milvus 等）
- ChromaDB（Phase 2 才引入）
- 超过 200 行的 MEMORY.md（超出必须立即运行 memory_rotate.py）
- 不在 `_index.md` 路由表里的孤儿文件

---

Last updated: 2026-03-15
