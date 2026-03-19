# BioOpenClaw 实现提示词手册

**使用方式**：Cursor + Claude Opus 4.6 | 2026-03-15

---

> **使用说明**
>
> 1. 每个步骤的「Cursor 提示词」区块可以直接复制粘贴到 Cursor 的对话框中执行。
> 2. 提示词中的 `@文件名` 是 Cursor 的文件引用语法——请确保对应文件在工作区中存在，Cursor 会自动将其内容注入上下文。
> 3. 建议按步骤顺序执行。每完成一步，确认产出符合预期后再进入下一步。
> 4. 如果某步产出不理想，可以直接在同一会话中追加修正指令，不必重新开始。
> 5. 长步骤（如 Step 3、Step 5）建议在单独的 Cursor 会话中执行，避免上下文溢出。

---

## 总览：实现路线图

```
Phase 0: 项目初始化
  └── Step 0.1  仓库 + Python 环境 + Cursor Rules
  └── Step 0.2  创建 AGENTS.md

Phase 1-P0: MCP 桥接验证（最高优先级）
  └── Step 1.1  Data Agent MCP Server 骨架
  └── Step 1.2  Scanpy 单细胞质控工具实现
  └── Step 1.3  MCP Server 端到端测试
  └── Step 1.4  MCP 客户端连接配置

Phase 1-Memory: 持久化记忆系统
  └── Step 2.1  目录结构 + 全部 SOUL.md
  └── Step 2.2  MEMORY.md / active_context.md / shared_memory 模板
  └── Step 2.3  记忆维护脚本（4个）

Phase 1-P1: Scout Agent + 模型注册表
  └── Step 3.1  Scout MCP Server（HuggingFace Hub 监控）
  └── Step 3.2  模型注册表自动生成 + 一致性校验

Phase 1-P2: Watcher 循环检测
  └── Step 4.1  Watcher 核心引擎（循环检测 + steering_queue）
  └── Step 4.2  Watcher 集成测试

Phase 1-P3: 数据层集成
  └── Step 5.1  lakeFS + LaminDB 集成原型
```

---

## Phase 0: 项目初始化

### Step 0.1 — 仓库初始化 + Python 环境 + Cursor Rules

**前置条件**：已安装 Python 3.10+、Git、Cursor IDE

**Cursor 提示词**：

```
我正在初始化一个名为 BioOpenClaw 的生物信息学多智能体框架项目。请帮我完成以下初始化工作：

1. 在当前工作区根目录初始化 git 仓库（如果还没有的话）

2. 创建 Python 项目结构：
   - pyproject.toml（项目名 bioopenclaw，Python >=3.10，暂时不填依赖）
   - requirements.txt 包含以下基础依赖（请查找最新版本号）：
     - scanpy
     - anndata
     - GEOparse
     - biopython
     - huggingface_hub
     - fastapi
     - uvicorn
     - pydantic
     - httpx
     - mcp（Model Context Protocol SDK，如果存在的话搜索 PyPI 确认包名）
   - .gitignore（Python 项目标准模板，额外忽略 .h5ad 文件、daily_log/archive/、__pycache__）

3. 创建 .cursor/rules/ 目录，写入以下 Cursor Rule 文件：

   a) .cursor/rules/project-context.md —— 内容如下：
      ---
      alwaysApply: true
      ---
      # BioOpenClaw 项目上下文
      
      BioOpenClaw 是一个基于多 OpenClaw 实例的 AI 生物信息科学家群系统。
      - 架构：5 个专精 Agent（Data / Model / Research / Scout / Watcher）+ 指挥层
      - 每个 Python Agent 封装为独立 MCP Server，通过 MCP 协议与 OpenClaw 通信
      - 记忆系统：三层 Markdown 架构（Always Loaded / Session Lifecycle / On-Demand）
      - 关键设计文档：BioOpenClaw_Framework_Design.pdf、BioOpenClaw_v0.2_优化设计文档_updated.docx、BioOpenClaw_v0.3_持久化记忆系统设计.md
      
      技术栈：Python 3.10+、Scanpy、AnnData、HuggingFace Hub、FastAPI、MCP Protocol

   b) .cursor/rules/coding-standards.md —— 内容如下：
      ---
      alwaysApply: true
      ---
      # 编码规范
      
      - 所有 Python 代码使用 type hints
      - 文档字符串使用 Google 风格
      - MCP Server 入口文件命名为 server.py
      - 每个 Agent 的 MCP tools 放在 tools/ 子目录
      - 配置使用 pydantic BaseSettings
      - 日志使用 Python logging 模块，格式包含时间戳和 Agent 名称
      - 错误处理：生物信息工具调用必须 try-except 并返回结构化错误信息
      - 所有文件使用 UTF-8 编码

4. 创建 src/ 目录结构（空的 __init__.py）：
   src/
   └── bioopenclaw/
       ├── __init__.py
       ├── mcp_servers/
       │   ├── __init__.py
       │   ├── data_agent/
       │   │   └── __init__.py
       │   ├── model_agent/
       │   │   └── __init__.py
       │   ├── research_agent/
       │   │   └── __init__.py
       │   └── scout_agent/
       │       └── __init__.py
       ├── watcher/
       │   └── __init__.py
       ├── orchestrator/
       │   └── __init__.py
       └── memory/
           └── __init__.py
```

**预期产出**：
- 可工作的 Git 仓库
- Python 项目骨架（pyproject.toml、requirements.txt、src/ 目录）
- Cursor Rules 已生效（后续会话自动加载项目上下文）

---

### Step 0.2 — 创建 AGENTS.md

**前置条件**：Step 0.1 完成

**Cursor 提示词**：

```
请在项目根目录创建 AGENTS.md 文件。

这是 BioOpenClaw 项目的 AI Agent 协作文档。内容应包含：

1. 项目简介（一段话）

2. 架构概览（文字描述，不需要图）：
   - 指挥层：人工指挥 + 轻量调度脚本
   - 5 个专精 Agent：Data / Model / Research / Scout / Watcher
   - 每个 Agent 封装为独立 MCP Server（Python）
   - 三层 Markdown 记忆系统

3. 目录结构速查（列出 src/、agents/、shared_memory/、scripts/ 的主要内容）

4. 开发约定：
   - MCP Server 开发：每个 Agent 在 src/bioopenclaw/mcp_servers/<agent_name>/ 下，入口 server.py
   - 记忆文件开发：在 agents/<agent_name>/ 和 shared_memory/ 下
   - 维护脚本：在 scripts/ 下
   - 测试：在 tests/ 下，与 src 结构镜像

5. 关键设计文档索引：
   - @BioOpenClaw_Framework_Design.pdf — v0.1 原始架构
   - @BioOpenClaw_v0.2_优化设计文档_updated.docx — v0.2 五实例扩展
   - @BioOpenClaw_v0.3_持久化记忆系统设计.md — v0.3 记忆系统

6. 当前 Phase：Phase 1 技术验证
   - P0：MCP 桥接验证
   - P1：Scout + 记忆层原型
   - P2：Watcher 循环检测
   - P3：数据层集成

保持简洁，总长度不超过 150 行。
```

**预期产出**：项目根目录下的 `AGENTS.md`，为后续所有 Cursor 会话提供持久项目上下文。

---

## Phase 1-P0: MCP 桥接验证

> **这是项目最高优先级任务。** v0.1 文档已识别"OpenClaw Node.js 运行时与 Python 生物信息工具的摩擦"为最大工程风险。解决方案是将每个 Python Agent 封装为独立 MCP Server。

### Step 1.1 — Data Agent MCP Server 骨架

**前置条件**：Step 0.1 完成

**Cursor 提示词**：

```
请阅读 @BioOpenClaw_Framework_Design.pdf 中关于 Data Agent 的设计（3.1 节），然后在 src/bioopenclaw/mcp_servers/data_agent/ 下创建一个 MCP Server 骨架。

具体要求：

1. server.py — MCP Server 入口：
   - 使用 Python MCP SDK（搜索最新的 mcp 或 modelcontextprotocol 包的用法）
   - 如果没有成熟的 Python MCP SDK，则使用 FastAPI 实现一个兼容 MCP 协议的 JSON-RPC 服务器
   - 服务器名称：bioopenclaw-data-agent
   - 监听端口：通过环境变量 DATA_AGENT_PORT 配置，默认 8001

2. tools/ 目录放具体工具实现，先创建空的结构：
   - tools/__init__.py
   - tools/scanpy_qc.py — 单细胞质控（下一步实现）
   - tools/geo_download.py — GEO 数据下载（占位）
   - tools/data_format.py — 数据格式转换（占位）

3. config.py — 使用 pydantic BaseSettings：
   - port: int = 8001
   - data_dir: str = "./data"（数据存放目录）
   - max_file_size_gb: float = 10.0

4. 在 server.py 中注册一个测试工具 ping，接收无参数，返回 {"status": "ok", "agent": "data_agent"}

请确保代码可以直接运行：python -m bioopenclaw.mcp_servers.data_agent.server
```

**预期产出**：可启动的 MCP Server 骨架，`ping` 工具可响应。

---

### Step 1.2 — Scanpy 单细胞质控工具

**前置条件**：Step 1.1 完成

**Cursor 提示词**：

```
请实现 src/bioopenclaw/mcp_servers/data_agent/tools/scanpy_qc.py，这是 Data Agent 的核心质控工具。

参考 @BioOpenClaw_Framework_Design.pdf 中 Data Agent 的核心能力描述：
"单细胞 RNA-seq 数据预处理（质控、归一化、批次校正）"

具体要求：

1. 实现一个函数 run_scanpy_qc，作为 MCP tool 暴露：
   - 输入参数（JSON Schema 定义）：
     - input_path: str — 输入 .h5ad 文件路径
     - output_path: str — 输出 .h5ad 文件路径
     - min_genes: int = 200 — 每个细胞的最少基因数
     - min_cells: int = 3 — 每个基因出现的最少细胞数
     - max_mt_pct: float = 20.0 — 线粒体基因最大百分比
     - n_top_genes: int = 2000 — 高变基因数量
     - normalize_target_sum: float = 1e4 — 归一化目标总数
   
   - 执行流程：
     a) 读取 .h5ad 文件（adata = sc.read_h5ad(input_path)）
     b) 基本过滤（sc.pp.filter_cells, sc.pp.filter_genes）
     c) 计算 QC 指标（线粒体基因百分比）
     d) 过滤高线粒体百分比的细胞
     e) 归一化（sc.pp.normalize_total）
     f) 对数转换（sc.pp.log1p）
     g) 高变基因选择（sc.pp.highly_variable_genes）
     h) 保存结果到 output_path
   
   - 返回值（结构化 JSON）：
     - status: "success" | "error"
     - cells_before: int
     - cells_after: int
     - genes_before: int
     - genes_after: int
     - n_highly_variable_genes: int
     - output_path: str
     - error_message: str | null

2. 在 server.py 中注册这个工具，名称为 scanpy_qc

3. 所有 scanpy 调用必须包裹在 try-except 中，异常时返回结构化错误而非崩溃

4. 添加日志记录：在质控流程的每个关键步骤记录 INFO 日志
```

**预期产出**：完整可用的 Scanpy 质控 MCP 工具，接收 h5ad 文件路径和参数，执行质控流程，返回结构化结果。

---

### Step 1.3 — MCP Server 端到端测试

**前置条件**：Step 1.2 完成

**Cursor 提示词**：

```
请为 Data Agent MCP Server 创建端到端测试。

1. 创建 tests/test_data_agent/ 目录

2. tests/test_data_agent/conftest.py：
   - 创建一个 pytest fixture，用 scanpy 的内置数据集（sc.datasets.pbmc3k() 或自己生成一个小的测试 AnnData）生成临时 .h5ad 文件
   - 创建一个 fixture 启动 Data Agent MCP Server（用 subprocess 在后台启动，测试结束后关闭）

3. tests/test_data_agent/test_scanpy_qc.py：
   - test_ping：调用 ping 工具，验证返回 {"status": "ok"}
   - test_scanpy_qc_success：调用 scanpy_qc 工具，传入测试 h5ad 文件路径和默认参数，验证：
     - 返回 status == "success"
     - cells_after <= cells_before
     - genes_after <= genes_before
     - 输出文件存在且可被 scanpy 读取
   - test_scanpy_qc_invalid_path：传入不存在的文件路径，验证返回 status == "error"
   - test_scanpy_qc_custom_params：使用自定义参数（min_genes=500, max_mt_pct=10），验证过滤更严格

4. 创建一个简单的 MCP 客户端辅助函数 tests/test_data_agent/mcp_client.py：
   - 封装对 MCP Server 的 HTTP/JSON-RPC 调用
   - call_tool(tool_name, params) -> dict

5. 在 pyproject.toml 或 setup.cfg 中配置 pytest

提供运行测试的命令。
```

**预期产出**：4 个通过的测试，验证 MCP Server 的完整工作链路。

---

### Step 1.4 — MCP 客户端连接配置

**前置条件**：Step 1.3 测试全部通过

**Cursor 提示词**：

```
请创建 MCP 客户端连接配置，使得外部（OpenClaw 或其他 MCP 客户端）可以连接到 Data Agent。

1. 在项目根目录创建 mcp_config.json，定义 Data Agent MCP Server 的连接方式：
   {
     "servers": {
       "bioopenclaw-data-agent": {
         "command": "python",
         "args": ["-m", "bioopenclaw.mcp_servers.data_agent.server"],
         "env": {
           "DATA_AGENT_PORT": "8001"
         }
       }
     }
   }

2. 在 README.md 中（如果不存在则创建）添加：
   - 项目简介
   - 快速开始：如何安装依赖、启动 Data Agent MCP Server、运行测试
   - MCP Server 列表和端口分配：
     - Data Agent: 8001
     - Model Agent: 8002
     - Research Agent: 8003  
     - Scout Agent: 8004
     - Watcher: 8005

3. 创建 scripts/start_data_agent.py 启动脚本：
   - 读取环境变量或命令行参数
   - 启动 MCP Server
   - 打印连接信息

此步骤完成后，P0（MCP 桥接验证）的核心目标达成：
"OpenClaw 能通过 MCP 调用 Scanpy 完成一次单细胞质控流程"
```

**预期产出**：完整的 MCP 连接配置，外部客户端可发现并调用 Data Agent。

---

## Phase 1-Memory: 持久化记忆系统

### Step 2.1 — 目录结构 + SOUL.md 文件

**前置条件**：Step 0.2 完成

**Cursor 提示词**：

```
请阅读 @BioOpenClaw_v0.3_持久化记忆系统设计.md 的第四节（4.3 目录结构），完整创建记忆系统的目录和 SOUL.md 文件。

1. 按照 v0.3 文档 4.3 节的目录结构，创建所有目录（agents/ 和 shared_memory/）。
   每个需要的子目录都要创建（topics/、daily_log/、corrections_log/ 等），空目录放一个 .gitkeep 文件。

2. 为每个 Agent 编写 SOUL.md 文件。参考以下来源：
   - Data Agent：参考 @BioOpenClaw_Framework_Design.pdf 第 3.1 节的 SOUL.md 行为边界草稿
   - Model Agent：参考 v0.1 第 3.2 节
   - Research Agent：参考 v0.1 第 3.3 节
   - Scout Agent：参考 @BioOpenClaw_v0.2_优化设计文档_updated.docx 第三节（3.5 SOUL.md 行为边界）
   - Watcher：参考 v0.2 第四节（4.5 SOUL.md 行为边界）

   每个 SOUL.md 应包含：
   - 角色定义（一句话）
   - 职责范围（3-5 条）
   - 行为边界（明确"不做什么"）
   - 协作规则（与哪些 Agent 交互、通过什么渠道）
   - 记忆系统使用规则（引用 MEMORY.md 和 active_context.md 的读写规范）

   保持每个 SOUL.md 在 50-80 行以内。用中文编写。
```

**预期产出**：完整的 `agents/` 和 `shared_memory/` 目录结构，5 个 Agent 各自的 `SOUL.md`。

---

### Step 2.2 — 记忆模板文件 + shared_memory 索引

**前置条件**：Step 2.1 完成

**Cursor 提示词**：

```
请阅读 @BioOpenClaw_v0.3_持久化记忆系统设计.md 的 4.4-4.6 节，创建所有记忆模板文件。

1. 为每个 Agent 创建 MEMORY.md 初始模板：
   - 按照 v0.3 文档 4.4 节的 MEMORY.md 规范
   - 包含 3 个固定 section：Topic Routing / Core Lessons / Active Warnings
   - Topic Routing 指向该 Agent 的 topics/ 子目录下的文件
   - Core Lessons 和 Active Warnings 初始为空（附一条注释说明格式要求）
   - 每个 Agent 的 Topic Routing 应反映其专业领域，例如：
     - Data Agent: GEO 下载、Scanpy 质控、批次校正
     - Model Agent: LoRA 微调、Triton 推理服务
     - Research Agent: 假设生成、统计检验
     - Scout Agent: HuggingFace 监控、基准测试追踪
     - Watcher: 循环检测、纠偏策略

2. 为每个 Agent 创建 active_context.md 初始模板：
   - 按照 v0.3 文档 4.5 节的规范
   - YAML front matter 包含 last_session
   - 4 个固定 section：Current Focus / Blocked / Next Steps / Recent Decisions
   - 所有 section 初始内容为"（暂无）"

3. 为每个 Agent 的 topics/ 目录创建初始 topic 文件：
   - 每个文件包含标题和空的骨架 section
   - 参考 v0.3 文档 4.6 节的 geo_download.md 示例作为格式参照

4. 创建 shared_memory/ 下的所有索引和模板：
   - _index.md：按照 v0.3 文档 4.4 节的 shared_memory/_index.md 示例
   - model_registry/_index.md：空的模型汇总表
   - literature/_index.md：空的文献索引
   - experiments/_index.md：空的实验索引
   - conventions.md：基本团队约定（数据格式用 AnnData .h5ad、消息格式用 YAML front matter 的 Markdown）
   - known_issues.md：空的已知问题列表

所有文件用中文编写。
```

**预期产出**：所有 Agent 的 MEMORY.md、active_context.md、topic 文件，以及 shared_memory 的完整索引体系。

---

### Step 2.3 — 记忆维护脚本

**前置条件**：Step 2.2 完成

**Cursor 提示词**：

```
请阅读 @BioOpenClaw_v0.3_持久化记忆系统设计.md 的 4.9 节（维护脚本设计），实现 4 个维护脚本。

创建在 scripts/ 目录下：

1. scripts/memory_rotate.py — 记忆轮换
   - 扫描 agents/*/MEMORY.md 文件
   - 如果 Core Lessons section 超过指定行数上限（默认从命令行参数读取，默认 200）
   - 将最旧的条目（底部的，因为按日期降序排列，最旧在最下面）移动到对应的 topic 文件
   - 移动时按 Topic Routing 表匹配关键词决定目标文件；如果无法匹配，放到 topics/general.md
   - 运行后打印报告：哪些 Agent 的 MEMORY.md 被轮换了，移动了多少条
   - 命令行接口：python scripts/memory_rotate.py [--max-lines 200] [--dry-run]

2. scripts/memory_consistency_check.py — 一致性校验
   - 检查项：
     a) 每个 _index.md 中引用的文件是否实际存在（检测幽灵索引）
     b) 每个目录下是否有未被任何 _index.md 引用的 .md 文件（检测孤儿文件，排除 SOUL.md / MEMORY.md / active_context.md / conventions.md / known_issues.md）
     c) 每个 MEMORY.md 的行数是否超过 200
     d) 每个 Core Lessons 条目是否以 [YYYY-MM-DD] 开头
   - 输出 JSON 格式的校验报告
   - 命令行接口：python scripts/memory_consistency_check.py [--fix]（--fix 模式自动修复 _index.md）
   - 退出码：0=全部通过，1=有警告，2=有错误

3. scripts/daily_log_archive.py — 日志归档
   - 扫描 agents/*/daily_log/ 和 agents/watcher/corrections_log/
   - 将超过 N 天（默认 14）的文件移动到对应的 archive/ 子目录
   - 命令行接口：python scripts/daily_log_archive.py [--days 14] [--dry-run]

4. scripts/memory_flush.py — 会话 Flush
   - 接收命令行参数：--agent <agent_name> --summary <text> --lessons <lesson1> <lesson2> ...
   - 执行：
     a) 用当前时间戳更新目标 Agent 的 active_context.md 的 YAML front matter
     b) 追加一条条目到今日的 daily_log（如果文件不存在则创建）
     c) 如果提供了 --lessons，将每条 lesson 追加到 MEMORY.md 的 Core Lessons section（带今日日期戳）
   - 这个脚本主要供调度层自动调用

所有脚本：
- 使用 argparse 处理命令行参数
- 使用 pathlib 处理文件路径
- 包含 if __name__ == "__main__" 入口
- 项目根目录通过自动检测（向上查找 pyproject.toml 或 AGENTS.md）确定
- 添加 --verbose 参数控制日志详细程度
```

**预期产出**：4 个可独立运行的维护脚本，完整覆盖记忆系统的生命周期管理。

---

## Phase 1-P1: Scout Agent + 模型注册表

### Step 3.1 — Scout MCP Server

**前置条件**：Step 1.1 完成（MCP Server 骨架模式已验证），Step 2.2 完成（shared_memory 目录已创建）

**Cursor 提示词**：

```
请阅读 @BioOpenClaw_v0.2_优化设计文档_updated.docx 中关于 Scout OpenClaw 的设计（第三节），然后创建 Scout Agent 的 MCP Server。

在 src/bioopenclaw/mcp_servers/scout_agent/ 下实现：

1. server.py — MCP Server 入口：
   - 服务器名称：bioopenclaw-scout-agent
   - 端口：环境变量 SCOUT_AGENT_PORT，默认 8004
   - 参考 Data Agent 的 server.py 结构

2. tools/hf_monitor.py — HuggingFace Hub 监控工具：
   - MCP tool 名称：scan_huggingface_models
   - 输入参数：
     - tags: list[str] — 搜索标签（如 ["biology", "single-cell", "protein"]）
     - authors: list[str] — 关注的作者（如 ["facebook", "bowang-lab", "ctheodoris"]）
     - days_back: int = 7 — 搜索最近 N 天发布/更新的模型
     - limit: int = 20
   - 使用 huggingface_hub 库的 HfApi().list_models() 接口
   - 返回：发现的模型列表，每个模型包含 model_id, author, tags, last_modified, downloads, likes

3. tools/registry_writer.py — 模型注册表写入工具：
   - MCP tool 名称：register_model
   - 输入参数：
     - model_id: str — HuggingFace 模型 ID
     - name: str — 显示名称
     - version: str
     - model_type: str — 如 "单细胞基础模型"、"蛋白质语言模型"
     - parameters: str — 如 "51.3M"
     - license: str
     - paper_url: str | None
     - benchmarks: list[dict] | None — [{benchmark, task, score, date}]
     - limitations: list[str] | None
   - 执行：
     a) 生成 shared_memory/model_registry/<name>.md 文件（YAML front matter + Markdown body）
     b) 更新 shared_memory/model_registry/_index.md 索引表
   - 格式参考 @BioOpenClaw_v0.3_持久化记忆系统设计.md 4.6 节的 scGPT.md 示例

4. config.py — Scout Agent 配置

5. 更新 mcp_config.json 添加 Scout Agent 的连接配置
```

**预期产出**：Scout Agent MCP Server，包含 HuggingFace 模型扫描和注册表写入两个工具。

---

### Step 3.2 — 模型注册表自动化 + 一致性校验集成

**前置条件**：Step 3.1 + Step 2.3 完成

**Cursor 提示词**：

```
请创建 Scout Agent 的自动化流程和集成测试。

1. scripts/scout_scan.py — 自动扫描脚本：
   - 启动 Scout Agent MCP Server
   - 调用 scan_huggingface_models 工具扫描最近 7 天的生物信息模型
   - 对每个新发现的模型，检查 shared_memory/model_registry/ 下是否已有同名文件
   - 对于新模型，调用 register_model 工具写入注册表
   - 运行 memory_consistency_check.py 验证一致性
   - 输出扫描报告：新增 N 个模型，更新 N 个，跳过 N 个已存在
   - 命令行接口：python scripts/scout_scan.py [--tags biology single-cell] [--days 7]

2. tests/test_scout_agent/ 测试：
   - test_hf_monitor.py：
     - test_scan_models：调用 scan_huggingface_models，验证返回格式正确
     - test_scan_with_filters：使用特定 tags 过滤，验证结果都包含对应 tag
   - test_registry_writer.py：
     - test_register_new_model：注册一个测试模型，验证 .md 文件和 _index.md 都正确生成
     - test_register_duplicate：重复注册同一模型，验证不会创建重复条目
     - test_consistency_after_register：注册后运行 memory_consistency_check，验证通过

3. 验证 P1 成功标准：
   "Scout 能自动发现上周新发布的生物基础模型，写入 model_registry Markdown 文件，并通过一致性校验"
```

**预期产出**：完整的 Scout 自动扫描流程，注册表写入，和一致性校验集成测试。

---

## Phase 1-P2: Watcher 循环检测

### Step 4.1 — Watcher 核心引擎

**前置条件**：Step 0.1 完成

**Cursor 提示词**：

```
请阅读 @BioOpenClaw_v0.2_优化设计文档_updated.docx 第四节（Watcher OpenClaw）的完整设计，实现 Watcher 的核心检测引擎。

在 src/bioopenclaw/watcher/ 下创建：

1. detector.py — 三层检测引擎：

   class WatcherDetector:
       """Watcher 三层检测引擎"""
       
       def __init__(self, config: WatcherConfig):
           # 层级 1 配置
           self.hash_window = config.hash_window  # 检查最近 N 次工具调用
           self.repeat_threshold = config.repeat_threshold  # 哈希重复 K 次触发
           self.max_tool_rounds = config.max_tool_rounds  # 硬迭代上限
           
           # 层级 2 配置
           self.similarity_threshold = config.similarity_threshold  # 输出相似度阈值
           self.stall_window = config.stall_window  # 停滞检测窗口
           
           # 内部状态
           self.tool_call_history: list[dict] = []
           self.output_history: list[str] = []
   
   实现以下方法：
   
   a) record_tool_call(tool_name: str, params: dict) -> DetectionResult | None
      - 记录工具调用到历史
      - 对 (tool_name, sorted params) 做 hash
      - 检查最近 hash_window 次调用中是否有 repeat_threshold 次重复
      - 检查总调用次数是否超过 max_tool_rounds
      - 返回 DetectionResult（包含 level, trigger_type, message）或 None
   
   b) record_output(output: str) -> DetectionResult | None
      - 记录输出到历史
      - 如果历史 >= stall_window 条，计算最近几条的两两相似度
      - 相似度计算用简单方案：SequenceMatcher 或字符级 Jaccard
      - 如果平均相似度 > similarity_threshold，判定为停滞
   
   c) reset() — 清空历史（新任务开始时调用）

2. steering.py — Steering Queue 纠偏机制：

   class SteeringQueue:
       """纠偏消息队列"""
       
       def __init__(self):
           self.queue: list[SteeringMessage] = []
       
       def inject(self, target_agent: str, message: str, priority: str, trigger: DetectionResult):
           """添加纠偏消息到队列"""
       
       def pop(self, target_agent: str) -> SteeringMessage | None:
           """取出目标 Agent 的下一条纠偏消息（在工具调用间隙注入）"""
       
       def log_correction(self, correction: CorrectionRecord):
           """将纠偏记录写入 agents/watcher/corrections_log/"""
           # 写入 corrections_log/YYYY-MM-DD.md
           # 格式参考 @BioOpenClaw_v0.3_持久化记忆系统设计.md 4.6 节的纠偏记录示例

3. models.py — 数据模型：
   - DetectionResult(level: int, trigger_type: str, message: str, details: dict)
   - SteeringMessage(target_agent: str, message: str, priority: str, created_at: datetime, trigger: DetectionResult)
   - CorrectionRecord(timestamp, target_agent, trigger, action, effect, domain_tags, priority)
   - WatcherConfig(hash_window=10, repeat_threshold=3, max_tool_rounds=50, similarity_threshold=0.95, stall_window=5)

4. config.py — WatcherConfig 使用 pydantic BaseSettings
```

**预期产出**：Watcher 的完整检测引擎和纠偏队列，可独立运行和测试。

---

### Step 4.2 — Watcher 集成测试

**前置条件**：Step 4.1 完成

**Cursor 提示词**：

```
请为 Watcher 引擎创建测试。

创建 tests/test_watcher/ 目录：

1. test_detector.py：
   - test_no_detection_normal_calls：正常的不同工具调用不应触发检测
   - test_detect_repeated_tool_calls：连续 3 次相同工具调用（同名同参数）应触发层级 1 检测
   - test_detect_max_rounds：超过 max_tool_rounds 次调用应触发层级 1 检测
   - test_detect_similar_outputs：5 次高度相似的输出应触发层级 2 检测
   - test_no_false_positive_different_params：相同工具名但不同参数不应触发
   - test_reset_clears_history：reset 后历史清空，不再触发之前的模式

2. test_steering.py：
   - test_inject_and_pop：注入消息后可以按 target_agent 取出
   - test_pop_empty：空队列返回 None
   - test_log_correction：验证纠偏记录正确写入 corrections_log 目录
   - test_correction_log_format：验证写入的 Markdown 文件格式符合 v0.3 设计规范

3. test_integration.py：
   - test_detect_and_steer_flow：完整流程测试：
     a) 创建 Detector 和 SteeringQueue
     b) 模拟 Data Agent 连续 3 次调用相同 BLAST 查询
     c) Detector 触发检测
     d) 自动注入纠偏消息到 SteeringQueue
     e) 取出消息，验证内容合理
     f) 记录纠偏结果到 corrections_log
     g) 验证 corrections_log 文件存在且格式正确

验证 P2 成功标准：
"Watcher 能在 5 轮内检测到重复工具调用并成功注入纠偏"
```

**预期产出**：完整的 Watcher 测试套件，覆盖三层检测和纠偏流程。

---

## Phase 1-P3: 数据层集成

### Step 5.1 — lakeFS + LaminDB 集成原型

**前置条件**：Step 1.2 完成（Scanpy 质控工具已可用）

**Cursor 提示词**：

```
请阅读 @BioOpenClaw_v0.2_优化设计文档_updated.docx 第五节（Data OpenClaw 四层数据架构），实现一个最小化的数据版本控制集成。

注意：lakeFS 和 LaminDB 都需要额外的服务部署。本步骤先实现一个抽象层，使得代码可以在无外部服务时以本地模式运行。

在 src/bioopenclaw/mcp_servers/data_agent/tools/ 下创建：

1. data_versioning.py — 数据版本控制抽象层：

   class DataVersionManager:
       """数据版本控制管理器（支持 lakeFS 和本地文件系统两种后端）"""
       
       def __init__(self, backend: str = "local"):
           # backend: "local" | "lakefs"
           # local 模式：用 Git 管理数据文件的版本（适合小数据集和开发阶段）
           # lakefs 模式：连接 lakeFS 服务（生产环境）
       
       def commit(self, file_path: str, message: str, metadata: dict) -> str:
           """提交一个数据文件版本，返回 commit ID"""
       
       def get_history(self, file_path: str) -> list[dict]:
           """获取文件的版本历史"""
       
       def checkout(self, file_path: str, commit_id: str) -> str:
           """检出指定版本的文件，返回文件路径"""

   local 模式实现：
   - commit：复制文件到 data/versions/<hash>/<filename>，在 data/versions/log.json 记录版本信息
   - get_history：读取 log.json
   - checkout：复制目标版本文件到工作目录

2. data_lineage.py — 数据谱系追踪：

   class LineageTracker:
       """数据谱系追踪器"""
       
       def record_transform(self, input_path: str, output_path: str,
                           operation: str, params: dict, code_ref: str):
           """记录一次数据转换操作"""
           # 写入 data/lineage/YYYY-MM-DD_<operation>.json
       
       def get_lineage(self, file_path: str) -> list[dict]:
           """查询文件的完整谱系链"""

3. 将 DataVersionManager 和 LineageTracker 集成到 scanpy_qc.py：
   - 质控前自动提交输入文件版本
   - 质控后自动提交输出文件版本
   - 自动记录谱系（输入 -> scanpy_qc -> 输出，含参数）

4. 创建 MCP 工具 data_version_history：
   - 输入：file_path
   - 返回：该文件的版本历史列表

5. 创建测试 tests/test_data_agent/test_data_versioning.py：
   - test_commit_and_history：提交文件并查看历史
   - test_checkout_version：检出旧版本
   - test_lineage_tracking：执行质控后查看谱系
   - test_qc_with_versioning：验证 scanpy_qc 工具自动记录了版本和谱系

验证 P3 成功标准：
"一个 AnnData 数据集的完整谱系可查询复现"
```

**预期产出**：数据版本控制和谱系追踪的本地模式实现，集成到 Scanpy 质控流程中。

---

## 附录 A: 快速参考 — 文件和端口

| Agent | MCP Server 路径 | 端口 | SOUL.md |
|-------|----------------|------|---------|
| Data Agent | `src/bioopenclaw/mcp_servers/data_agent/` | 8001 | `agents/data_agent/SOUL.md` |
| Model Agent | `src/bioopenclaw/mcp_servers/model_agent/` | 8002 | `agents/model_agent/SOUL.md` |
| Research Agent | `src/bioopenclaw/mcp_servers/research_agent/` | 8003 | `agents/research_agent/SOUL.md` |
| Scout Agent | `src/bioopenclaw/mcp_servers/scout_agent/` | 8004 | `agents/scout_agent/SOUL.md` |
| Watcher | `src/bioopenclaw/watcher/` | 8005 | `agents/watcher/SOUL.md` |

| 维护脚本 | 功能 | 建议频率 |
|---------|------|---------|
| `scripts/memory_rotate.py` | MEMORY.md 轮换 | 每周 |
| `scripts/memory_consistency_check.py` | 索引一致性校验 | 每日 |
| `scripts/daily_log_archive.py` | 日志归档 | 每日 |
| `scripts/memory_flush.py` | 会话 Flush | 每次会话结束 |
| `scripts/scout_scan.py` | HuggingFace 扫描 | 每日 |

---

## 附录 B: Cursor 会话管理建议

| 建议 | 说明 |
|------|------|
| 一个步骤一个会话 | 避免上下文过长导致精度下降。每完成一步，开新会话执行下一步。 |
| 善用 @文件引用 | 每个提示词中都用 @ 引用相关设计文档和已有代码文件，让 Claude 有完整上下文。 |
| 先测试再继续 | 每个 Step 完成后运行测试或手动验证，确认无误再进入下一步。 |
| AGENTS.md 是锚点 | AGENTS.md 在每个会话中自动加载，确保 Claude 始终知道项目全貌。 |
| 出错时追加修正 | 如果某步产出有问题，在同一会话中直接说明问题让 Claude 修正，而非从头开始。 |
| 使用 Plan 模式 | 对复杂步骤（如 Step 4.1），可以先切换到 Plan 模式让 Claude 给出实现计划，确认后再切回 Agent 模式执行。 |

---

## 附录 C: 后续 Phase 2-3 预告

Phase 1 全部完成后，后续步骤（按需实施）：

**Phase 2 — 语义检索加速：**
- 对 shared_memory/model_registry/ 和 literature/ 建立 ChromaDB 嵌入索引
- 触发条件：model_registry 超过 50 个条目

**Phase 3 — 知识图谱演进：**
- 引入 Graphiti 时序知识图谱
- MD 文件内容定期同步到图谱
- 触发条件：跨实例关联查询成为频繁需求

这些步骤的提示词将在 Phase 1 完成后的下一版手册中提供。
