"""Data Agent MCP Server — exposes bioinformatics data tools via MCP.

Start via CLI::

    python -m bioopenclaw.mcp_servers.data_agent.server

Or via the registered entry point::

    data-agent-server
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from bioopenclaw.mcp_servers.data_agent.config import get_config
from bioopenclaw.mcp_servers.data_agent.tools.batch_correction import run_batch_correction
from bioopenclaw.mcp_servers.data_agent.tools.cellxgene_query import query_cellxgene
from bioopenclaw.mcp_servers.data_agent.tools.data_inspector import inspect_dataset
from bioopenclaw.mcp_servers.data_agent.tools.dataset_search import search_datasets
from bioopenclaw.mcp_servers.data_agent.tools.format_converter import convert_data_format
from bioopenclaw.mcp_servers.data_agent.tools.geo_download import download_geo_data
from bioopenclaw.mcp_servers.data_agent.tools.multiome_process import process_multiome
from bioopenclaw.mcp_servers.data_agent.tools.normalize import normalize_data
from bioopenclaw.mcp_servers.data_agent.tools.pdb_query import query_pdb
from bioopenclaw.mcp_servers.data_agent.tools.pipeline import run_pipeline
from bioopenclaw.mcp_servers.data_agent.tools.qc_report import generate_qc_report
from bioopenclaw.mcp_servers.data_agent.tools.scanpy_qc import run_scanpy_qc
from bioopenclaw.mcp_servers.data_agent.tools.tcga_download import download_tcga_data
from bioopenclaw.mcp_servers.data_agent.tools.uniprot_query import query_uniprot
from bioopenclaw.mcp_servers.data_agent.tools.version_manager import (
    create_snapshot,
    list_versions,
    restore_version,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

cfg = get_config()
server = Server(cfg.server_name)

# ── Tool registry ──────────────────────────────────────────────────────────

TOOLS: list[Tool] = [
    Tool(
        name="run_scanpy_qc",
        description=(
            "对单细胞 RNA-seq 数据（.h5ad）执行 Scanpy 质控。"
            "过滤低质量细胞（基于最小基因数、线粒体比例），可选 doublet 检测（Scrublet）。"
            "内置数据验证：自动检测线粒体基因前缀、log 状态、QC 后细胞/基因数断言。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "input_path": {"type": "string", "description": "输入 .h5ad 文件路径"},
                "output_path": {"type": "string", "description": "输出 .h5ad 文件路径"},
                "min_genes": {"type": "integer", "description": "每个细胞最少基因数（默认 200）", "default": 200},
                "min_cells": {"type": "integer", "description": "每个基因最少细胞数（默认 3）", "default": 3},
                "mt_pct_threshold": {"type": "number", "description": "线粒体基因比例上限%（默认 20.0）", "default": 20.0},
                "run_scrublet": {"type": "boolean", "description": "是否运行 Scrublet doublet 检测", "default": False},
                "normalize": {"type": "boolean", "description": "QC 后是否归一化+log1p", "default": False},
                "find_hvg": {"type": "boolean", "description": "是否寻找高变基因", "default": False},
                "project": {"type": "string", "description": "项目名（用于谱系追踪）"},
            },
            "required": ["input_path", "output_path"],
        },
    ),
    Tool(
        name="download_geo_data",
        description=(
            "从 NCBI GEO 下载数据集（使用 GEOparse）。"
            "内置重试机制和 checksum 校验。自动检测数据格式提示（log2/counts/TPM）。"
            "需要设置 DATA_AGENT_ENTREZ_EMAIL 环境变量。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "gse_id": {"type": "string", "description": "GEO 系列 ID（如 'GSE123456'）"},
                "output_dir": {"type": "string", "description": "下载目录（默认 data/raw/<gse_id>/）"},
                "email": {"type": "string", "description": "NCBI 邮箱（可选，优先使用环境变量）"},
                "download_supplementary": {"type": "boolean", "description": "是否下载附加文件", "default": False},
                "project": {"type": "string", "description": "项目名（用于谱系追踪）"},
            },
            "required": ["gse_id"],
        },
    ),
    Tool(
        name="inspect_dataset",
        description=(
            "检视 .h5ad 数据集：返回 shape、数据单位（counts/TPM/FPKM）、log 状态、"
            "线粒体基因信息、潜在批次列、稀疏度、每细胞基因数分布。"
            "提供针对性的下游处理建议。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": ".h5ad 文件路径"},
            },
            "required": ["file_path"],
        },
    ),
    Tool(
        name="normalize_data",
        description=(
            "归一化 AnnData 数据。支持 scanpy_default（normalize_total+log1p）、"
            "log1p_only、total_only 三种方法。"
            "自动检测 log 状态，防止重复 log1p。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "input_path": {"type": "string", "description": "输入 .h5ad 文件路径"},
                "output_path": {"type": "string", "description": "输出 .h5ad 文件路径"},
                "method": {
                    "type": "string",
                    "description": "归一化方法",
                    "enum": ["scanpy_default", "log1p_only", "total_only"],
                    "default": "scanpy_default",
                },
                "target_sum": {"type": "number", "description": "normalize_total 目标总数（默认 1e4）", "default": 10000},
                "check_log_state": {"type": "boolean", "description": "是否自动检测 log 状态", "default": True},
                "project": {"type": "string", "description": "项目名（用于谱系追踪）"},
            },
            "required": ["input_path", "output_path"],
        },
    ),
    Tool(
        name="convert_data_format",
        description=(
            "将生信数据格式转换为 AnnData .h5ad。"
            "支持：10x_mtx（Market Exchange 目录）、csv、tsv、loom、h5（10x HDF5）。"
            "转换后自动验证 AnnData 完整性。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "input_path": {"type": "string", "description": "输入文件/目录路径"},
                "output_path": {"type": "string", "description": "输出 .h5ad 文件路径"},
                "input_format": {
                    "type": "string",
                    "description": "输入格式",
                    "enum": ["10x_mtx", "csv", "tsv", "loom", "h5", "h5ad"],
                },
                "gene_column": {"type": "string", "description": "CSV/TSV 中的基因名列（可选）"},
                "delimiter": {"type": "string", "description": "CSV/TSV 分隔符（可选，自动检测）"},
                "project": {"type": "string", "description": "项目名（用于谱系追踪）"},
            },
            "required": ["input_path", "output_path", "input_format"],
        },
    ),
    Tool(
        name="search_datasets",
        description=(
            "根据研究方案智能搜索数据集。并行查询 GEO、TCGA、CellxGene Census。"
            "输入关键词+物种+数据类型，返回按样本数排序的候选数据集列表。"
            "每个结果包含 ID、标题、物种、样本数、平台、摘要。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "研究关键词（如 ['BRCA1', 'single cell', 'breast cancer']）",
                },
                "organism": {"type": "string", "description": "物种（默认 'Homo sapiens'）", "default": "Homo sapiens"},
                "data_type": {
                    "type": "string",
                    "description": "数据类型",
                    "enum": ["scRNA-seq", "bulk-RNA-seq", "spatial", "CITE-seq", "ATAC-seq"],
                    "default": "scRNA-seq",
                },
                "min_samples": {"type": "integer", "description": "最少样本数（默认 3）", "default": 3},
                "sources": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["geo", "tcga", "cellxgene"]},
                    "description": "搜索数据源（默认全部）",
                },
                "max_results": {"type": "integer", "description": "最大返回数（默认 10）", "default": 10},
            },
            "required": ["keywords"],
        },
    ),
    Tool(
        name="download_tcga_data",
        description=(
            "从 TCGA (GDC API) 下载基因表达数据。"
            "支持按项目名（如 TCGA-BRCA）、数据类型、workflow 过滤。"
            "可选合并为 AnnData 格式。内置重试和文件清单记录。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "TCGA 项目 ID（如 'TCGA-BRCA'）"},
                "data_category": {"type": "string", "description": "数据类别（默认 'Transcriptome Profiling'）", "default": "Transcriptome Profiling"},
                "data_type": {"type": "string", "description": "数据类型（默认 'Gene Expression Quantification'）", "default": "Gene Expression Quantification"},
                "workflow_type": {"type": "string", "description": "Workflow（默认 'STAR - Counts'）", "default": "STAR - Counts"},
                "output_dir": {"type": "string", "description": "下载目录（默认 data/raw/<project>/）"},
                "max_files": {"type": "integer", "description": "最大下载文件数（默认 50）", "default": 50},
                "merge_to_anndata": {"type": "boolean", "description": "是否合并为 AnnData", "default": False},
                "project_name": {"type": "string", "description": "项目名（用于谱系追踪）"},
            },
            "required": ["project"],
        },
    ),
    Tool(
        name="query_cellxgene",
        description=(
            "查询 CellxGene Census 数据集。"
            "按物种、组织、疾病、细胞类型、测序方法过滤。"
            "默认返回元数据，设置 download=True 可下载表达数据为 AnnData。"
            "CellxGene Census 包含 16 亿+ 单细胞数据。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "organism": {"type": "string", "description": "物种（默认 'Homo sapiens'）", "default": "Homo sapiens"},
                "tissue": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "组织类型（如 ['breast', 'lung']）",
                },
                "disease": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "疾病类型（如 ['breast cancer']）",
                },
                "cell_type": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "细胞类型（如 ['T cell', 'B cell']）",
                },
                "assay": {"type": "string", "description": "测序方法（如 \"10x 3' v3\"）"},
                "max_results": {"type": "integer", "description": "最大返回集合数（默认 20）", "default": 20},
                "download": {"type": "boolean", "description": "是否下载表达数据（需 cellxgene-census）", "default": False},
                "max_cells": {"type": "integer", "description": "下载时最大细胞数（默认 100000）", "default": 100000},
                "output_dir": {"type": "string", "description": "下载目录"},
                "project": {"type": "string", "description": "项目名（用于谱系追踪）"},
            },
            "required": [],
        },
    ),
    Tool(
        name="run_batch_correction",
        description=(
            "对单细胞数据执行批次校正。"
            "支持 Harmony（快，嵌入空间）、Combat（修正表达矩阵，适合 DE 分析）、"
            "scVI（深度学习，强校正力）。"
            "自动验证 batch_key 和 batch 数量。自动计算 PCA 和 UMAP。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "input_path": {"type": "string", "description": "输入 .h5ad 文件路径"},
                "output_path": {"type": "string", "description": "输出 .h5ad 文件路径"},
                "batch_key": {"type": "string", "description": "obs 中的批次列名"},
                "method": {
                    "type": "string",
                    "description": "批次校正方法",
                    "enum": ["harmony", "combat", "scvi"],
                    "default": "harmony",
                },
                "n_pcs": {"type": "integer", "description": "PCA 维度数（默认 30）", "default": 30},
                "project": {"type": "string", "description": "项目名（用于谱系追踪）"},
            },
            "required": ["input_path", "output_path", "batch_key"],
        },
    ),
    Tool(
        name="generate_qc_report",
        description=(
            "生成 Markdown 格式的 QC 报告。"
            "报告包含：数据集摘要、数据单位、log 状态、QC 指标分布、"
            "前后对比（如提供 QC 后文件）、潜在批次列、下游建议。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "input_path": {"type": "string", "description": "输入 .h5ad 文件路径（QC 前或单独数据集）"},
                "output_path": {"type": "string", "description": "QC 后 .h5ad 文件路径（可选，用于前后对比）"},
                "report_path": {"type": "string", "description": "报告输出路径 .md（默认 data/reports/）"},
                "project": {"type": "string", "description": "项目名（用于谱系追踪）"},
            },
            "required": ["input_path"],
        },
    ),
    Tool(
        name="run_pipeline",
        description=(
            "执行多步骤数据处理管道。自动将上一步的输出传递给下一步。"
            "记录完整谱系和实验记录到 shared_memory/experiments/。"
            "配置格式：{name, project, steps: [{tool, params}], output_dir}"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "pipeline_config": {
                    "type": "object",
                    "description": "管道配置，包含 name、project、steps 数组和 output_dir",
                    "properties": {
                        "name": {"type": "string", "description": "管道名称"},
                        "project": {"type": "string", "description": "项目名（用于谱系追踪）"},
                        "steps": {
                            "type": "array",
                            "description": "步骤列表",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "tool": {"type": "string", "description": "工具名称"},
                                    "params": {"type": "object", "description": "工具参数"},
                                },
                                "required": ["tool"],
                            },
                        },
                        "output_dir": {"type": "string", "description": "输出目录"},
                    },
                    "required": ["name", "steps"],
                },
            },
            "required": ["pipeline_config"],
        },
    ),
    Tool(
        name="query_uniprot",
        description=(
            "搜索 UniProt 蛋白质数据库。"
            "支持按基因名、蛋白名、关键词搜索，可过滤物种和审核状态。"
            "可选下载 FASTA 序列文件。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索词（基因名/蛋白名/关键词）"},
                "organism": {"type": "string", "description": "物种（如 'Homo sapiens' 或 NCBI Taxonomy ID '9606'）"},
                "reviewed_only": {"type": "boolean", "description": "仅搜索 Swiss-Prot 审核条目", "default": True},
                "max_results": {"type": "integer", "description": "最大返回数", "default": 10},
                "download_fasta": {"type": "boolean", "description": "是否下载 FASTA 序列", "default": False},
                "output_dir": {"type": "string", "description": "FASTA 下载目录"},
                "project": {"type": "string", "description": "项目名（用于谱系追踪）"},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="query_pdb",
        description=(
            "搜索 RCSB PDB 蛋白质结构数据库。"
            "支持按蛋白名/基因名/UniProt ID 搜索，可按实验方法和分辨率过滤。"
            "可选下载 PDB/mmCIF 结构文件。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索词（蛋白名/基因名/UniProt ID）"},
                "organism": {"type": "string", "description": "物种学名"},
                "method": {"type": "string", "description": "实验方法（如 'X-RAY DIFFRACTION'）"},
                "resolution_max": {"type": "number", "description": "最大分辨率（Å）"},
                "max_results": {"type": "integer", "description": "最大返回数", "default": 10},
                "download_structure": {"type": "boolean", "description": "是否下载结构文件", "default": False},
                "file_format": {"type": "string", "description": "下载格式", "enum": ["pdb", "cif"], "default": "pdb"},
                "output_dir": {"type": "string", "description": "下载目录"},
                "project": {"type": "string", "description": "项目名（用于谱系追踪）"},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="process_multiome",
        description=(
            "处理多组学单细胞数据（CITE-seq / Multiome / Spatial）。"
            "使用 Muon (MuData) 读取多模态数据，各模态独立 QC，"
            "可选多模态整合。输出 .h5mu 格式。需要安装 muon。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "input_paths": {
                    "type": "object",
                    "description": "模态名到文件路径的映射（如 {\"rna\": \"rna.h5ad\", \"adt\": \"adt.h5ad\"} 或 {\"mudata\": \"combined.h5mu\"}）",
                },
                "output_path": {"type": "string", "description": "输出 .h5mu 文件路径"},
                "modalities": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要处理的模态列表（默认全部）",
                },
                "qc_rna": {"type": "object", "description": "RNA QC 参数 {min_genes, min_cells, mt_pct}"},
                "qc_protein": {"type": "object", "description": "ADT/蛋白 QC 参数 {min_counts}"},
                "run_integration": {"type": "boolean", "description": "是否运行多模态整合", "default": False},
                "project": {"type": "string", "description": "项目名（用于谱系追踪）"},
            },
            "required": ["input_paths", "output_path"],
        },
    ),
    Tool(
        name="create_snapshot",
        description=(
            "创建数据文件的版本快照。"
            "将文件复制到 data/versions/<project>/<tag>/ 并记录元数据（checksum, 时间戳）。"
            "Phase 1 的本地版本管理方案。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "要快照的文件路径"},
                "project": {"type": "string", "description": "项目名"},
                "tag": {"type": "string", "description": "版本标签（如 'v1', 'pre_qc', 'after_batch_correction'）"},
                "description": {"type": "string", "description": "版本描述"},
            },
            "required": ["file_path", "project", "tag"],
        },
    ),
    Tool(
        name="list_versions",
        description="列出项目的所有版本快照（标签、文件名、大小、时间）。",
        inputSchema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "项目名"},
            },
            "required": ["project"],
        },
    ),
    Tool(
        name="restore_version",
        description=(
            "从版本快照恢复数据文件。"
            "默认恢复到原始路径，也可指定新路径。恢复后自动验证 checksum。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "项目名"},
                "tag": {"type": "string", "description": "要恢复的版本标签"},
                "restore_to": {"type": "string", "description": "恢复到的目标路径（可选，默认恢复到原路径）"},
            },
            "required": ["project", "tag"],
        },
    ),
]

# Dispatch table
TOOL_HANDLERS: dict[str, Any] = {
    "run_scanpy_qc": run_scanpy_qc,
    "download_geo_data": download_geo_data,
    "inspect_dataset": inspect_dataset,
    "normalize_data": normalize_data,
    "convert_data_format": convert_data_format,
    "search_datasets": search_datasets,
    "download_tcga_data": download_tcga_data,
    "query_cellxgene": query_cellxgene,
    "run_batch_correction": run_batch_correction,
    "generate_qc_report": generate_qc_report,
    "run_pipeline": run_pipeline,
    "query_uniprot": query_uniprot,
    "query_pdb": query_pdb,
    "process_multiome": process_multiome,
    "create_snapshot": create_snapshot,
    "list_versions": list_versions,
    "restore_version": restore_version,
}


@server.list_tools()
async def handle_list_tools() -> ListToolsResult:
    return ListToolsResult(tools=TOOLS)


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
    logger.info(
        "Tool call: %s | args: %s",
        name,
        json.dumps(arguments, ensure_ascii=False, default=str)[:300],
    )

    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        result = {"success": False, "error": f"Unknown tool: {name}"}
    else:
        result = await handler(**arguments)

    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False, indent=2, default=str),
            )
        ]
    )


async def _run() -> None:
    cfg.ensure_dirs()
    logger.info("Data Agent MCP Server starting...")
    logger.info("Available tools: %s", ", ".join(TOOL_HANDLERS.keys()))

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    import asyncio
    asyncio.run(_run())


if __name__ == "__main__":
    main()
