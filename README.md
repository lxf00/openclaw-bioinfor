# BioOpenClaw — Data Agent

Multi-AI 生物信息科学家框架中的 **数据工程师 Agent**。负责从 GEO、TCGA、CellxGene Census 获取数据，执行 Scanpy QC、批次校正、归一化，输出标准化的 AnnData (.h5ad) 文件。

## Quick Start

### 1. 安装

```bash
# 基础安装
pip install -e .

# 含批次校正和 CellxGene 支持
pip install -e ".[batch-correction,cellxgene]"

# 开发环境（含测试工具）
pip install -e ".[dev]"
```

### 2. 配置环境变量

```bash
# 必填：NCBI API 需要邮箱
export DATA_AGENT_ENTREZ_EMAIL="your@email.com"

# 推荐：提升 NCBI API 速率（3 req/s → 10 req/s）
export DATA_AGENT_NCBI_API_KEY="your_api_key"

# 可选：自定义数据目录
export DATA_AGENT_DATA_DIR="./data"
```

或创建项目根目录下的 `.env` 文件：

```ini
DATA_AGENT_ENTREZ_EMAIL=your@email.com
DATA_AGENT_NCBI_API_KEY=your_api_key
```

### 3. 验证安装

```bash
python scripts/test_mcp_connection.py
```

### 4. 启动 MCP Server

```bash
# 方式 1: 通过 entry point
data-agent-server

# 方式 2: 通过 module
python -m bioopenclaw.mcp_servers.data_agent.server
```

### 5. 在 OpenClaw 中配置

将 `mcp_config.json` 的 `data-agent` 配置添加到 OpenClaw 的 MCP 服务器设置中。

## 可用工具（10 个 MCP 工具）

### 数据发现

| 工具 | 功能 |
|------|------|
| `search_datasets` | 智能搜索 GEO + TCGA + CellxGene |
| `download_geo_data` | GEO 数据下载（含 checksum + 重试） |
| `download_tcga_data` | TCGA 数据下载（GDC API） |
| `query_cellxgene` | CellxGene Census 查询和下载 |

### 数据处理

| 工具 | 功能 |
|------|------|
| `run_scanpy_qc` | Scanpy QC（自动 mt 前缀 + 可选 doublet 检测） |
| `normalize_data` | 归一化（防重复 log1p） |
| `convert_data_format` | 格式转换（10x_mtx/csv/loom → h5ad） |
| `run_batch_correction` | 批次校正（Harmony / Combat / scVI） |

### 数据管理

| 工具 | 功能 |
|------|------|
| `inspect_dataset` | 数据检视（shape, 单位, log 状态, 批次列） |
| `generate_qc_report` | QC 报告生成（Markdown） |

### 管道编排

| 工具 | 功能 |
|------|------|
| `run_pipeline` | 多步骤自动执行 + 谱系记录 + 实验记录 |

## 项目结构

```
src/bioopenclaw/mcp_servers/data_agent/
├── server.py          # MCP Server 入口
├── config.py          # pydantic-settings 配置
└── tools/
    ├── scanpy_qc.py       # QC
    ├── geo_download.py    # GEO 下载
    ├── tcga_download.py   # TCGA 下载
    ├── cellxgene_query.py # CellxGene 查询
    ├── dataset_search.py  # 智能搜索
    ├── batch_correction.py # 批次校正
    ├── normalize.py       # 归一化
    ├── format_converter.py # 格式转换
    ├── data_inspector.py  # 数据检视
    ├── qc_report.py       # QC 报告
    ├── pipeline.py        # 管道编排
    ├── validators.py      # 数据验证检查点
    └── lineage.py         # 谱系追踪
```

## 数据目录

```
data/
├── raw/        # 原始下载数据
├── processed/  # 处理后 .h5ad 文件
├── reports/    # QC 报告 (.md)
├── lineage/    # 谱系追踪记录 (.json)
└── versions/   # 本地版本管理
```

## 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `DATA_AGENT_ENTREZ_EMAIL` | 是 | — | NCBI Entrez API 邮箱 |
| `DATA_AGENT_NCBI_API_KEY` | 否 | — | NCBI API Key（提升速率限制） |
| `DATA_AGENT_PORT` | 否 | 8001 | 服务端口 |
| `DATA_AGENT_DATA_DIR` | 否 | ./data | 数据根目录 |
| `DATA_AGENT_RAW_DATA_DIR` | 否 | ./data/raw | 原始数据目录 |
| `DATA_AGENT_PROCESSED_DATA_DIR` | 否 | ./data/processed | 处理后数据目录 |
| `DATA_AGENT_REPORTS_DIR` | 否 | ./data/reports | 报告目录 |
| `DATA_AGENT_LINEAGE_DIR` | 否 | ./data/lineage | 谱系目录 |
| `DATA_AGENT_MAX_FILE_SIZE_GB` | 否 | 10.0 | 最大文件大小 |
| `DATA_AGENT_DOWNLOAD_TIMEOUT_SECONDS` | 否 | 3600 | 下载超时 |
| `DATA_AGENT_DOWNLOAD_MAX_RETRIES` | 否 | 3 | 下载重试次数 |
| `DATA_AGENT_DOWNLOAD_RETRY_DELAY_SECONDS` | 否 | 30 | 重试间隔 |
| `DATA_AGENT_API_RATE_LIMIT_PER_SECOND` | 否 | 3.0 | API 速率限制 |
| `DATA_AGENT_DEFAULT_ORGANISM` | 否 | Homo sapiens | 默认物种 |
| `DATA_AGENT_DEFAULT_QC_MIN_GENES` | 否 | 200 | 默认 QC 最小基因数 |
| `DATA_AGENT_DEFAULT_QC_MIN_CELLS` | 否 | 3 | 默认 QC 最小细胞数 |
| `DATA_AGENT_DEFAULT_QC_MT_PCT` | 否 | 20.0 | 默认线粒体比例阈值 |
| `DATA_AGENT_DEFAULT_BATCH_METHOD` | 否 | harmony | 默认批次校正方法 |

## 运行测试

```bash
# 全部离线测试
python -m pytest tests/test_data_agent/ -v

# 含网络测试（需要网络）
python -m pytest tests/test_data_agent/ -v --online
```

## 系统提示词

Data Agent 的 OpenClaw 系统提示词位于 `openclaw_configs/data_agent/system_prompt.md`。

## 设计文档

- 独立工作版设计: `DataAgent_Standalone_Design.md`
- 框架设计 v0.1: `BioOpenClaw_Framework_Design.pdf`
- 优化设计 v0.2: `BioOpenClaw_v0.2_优化设计文档_updated.docx`
- 记忆系统 v0.3: `BioOpenClaw_v0.3_持久化记忆系统设计.md`
