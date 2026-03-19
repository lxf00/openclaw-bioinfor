"""
mcp_server/server.py — BioOpenClaw MCP Python 服务器（P0 核心）

功能：通过 MCP 协议向 OpenClaw（Node.js）暴露生信工具：
  - run_scanpy_qc: Scanpy 质控流程
  - download_geo_data: GEO 数据下载
  - query_huggingface: HuggingFace 模型搜索
  - search_literature: 文献搜索（PubMed）

依赖安装：
  pip install mcp scanpy geoparse huggingface-hub biopython anndata

启动方式：
  python mcp_server/server.py

或通过 Claude Code 的 CLAUDE.md 配置 MCP 服务器（参见 IMPLEMENTATION_PROMPTS.md Step 6）

协议：MCP（Model Context Protocol）v1.0
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

# MCP SDK
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolResult,
    ListToolsResult,
    TextContent,
    Tool,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent

server = Server("bioinformatics-tools")


# ─────────────────────────────────────────────────────────────────────────────
# Tool: run_scanpy_qc
# ─────────────────────────────────────────────────────────────────────────────

async def _run_scanpy_qc(
    input_path: str,
    output_path: str,
    min_genes: int = 200,
    min_cells: int = 3,
    mt_pct_threshold: float = 20.0,
) -> dict[str, Any]:
    """执行 Scanpy 单细胞 QC 流程。"""
    try:
        import anndata
        import scanpy as sc
        import numpy as np
    except ImportError as e:
        return {"success": False, "error": f"依赖未安装: {e}"}

    input_file = Path(input_path)
    if not input_file.exists():
        return {"success": False, "error": f"输入文件不存在: {input_path}"}

    logger.info(f"开始 QC: {input_path}")
    adata = sc.read_h5ad(input_path)
    initial_cells = adata.n_obs

    # 计算 QC 指标
    adata.var["mt"] = adata.var_names.str.startswith("MT-")
    sc.pp.calculate_qc_metrics(adata, qc_vars=["mt"], percent_top=None, log1p=False, inplace=True)

    # 过滤
    sc.pp.filter_cells(adata, min_genes=min_genes)
    sc.pp.filter_genes(adata, min_cells=min_cells)
    adata = adata[adata.obs["pct_counts_mt"] < mt_pct_threshold].copy()

    filtered_cells = adata.n_obs

    # 保存
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    adata.write_h5ad(output_path)

    result = {
        "success": True,
        "initial_cells": initial_cells,
        "filtered_cells": filtered_cells,
        "removed_cells": initial_cells - filtered_cells,
        "removal_rate": f"{(initial_cells - filtered_cells) / initial_cells * 100:.1f}%",
        "genes_remaining": adata.n_vars,
        "output_path": str(output_file.absolute()),
        "qc_params": {
            "min_genes": min_genes,
            "min_cells": min_cells,
            "mt_pct_threshold": mt_pct_threshold,
        },
    }
    logger.info(f"QC 完成: {initial_cells} → {filtered_cells} 细胞")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Tool: download_geo_data
# ─────────────────────────────────────────────────────────────────────────────

async def _download_geo_data(
    gse_id: str,
    output_dir: str,
    email: str | None = None,
) -> dict[str, Any]:
    """从 GEO 下载数据集（使用 GEOparse）。"""
    try:
        import GEOparse
    except ImportError:
        return {"success": False, "error": "GEOparse 未安装：pip install GEOparse"}

    email = email or os.environ.get("ENTREZ_EMAIL", "")
    if not email:
        return {
            "success": False,
            "error": "必须设置 ENTREZ_EMAIL 环境变量或传入 email 参数",
        }

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info(f"开始下载 GEO 数据集: {gse_id}")
    try:
        gse = GEOparse.get_GEO(geo=gse_id, destdir=str(output_path), how="brief")
        gsms = list(gse.gsms.keys())
        gpl_info = list(gse.gpls.keys())

        result = {
            "success": True,
            "gse_id": gse_id,
            "title": gse.metadata.get("title", ["Unknown"])[0],
            "organism": gse.metadata.get("sample_organism_ch1", ["Unknown"])[0],
            "gsm_count": len(gsms),
            "gsm_ids": gsms[:5],  # 仅返回前5个示例
            "platform": gpl_info,
            "output_dir": str(output_path.absolute()),
            "warning": (
                "GEO 系列矩阵文件可能是 log2 转换过的，请检查后再做 log1p 变换"
            ),
        }
        logger.info(f"下载完成: {gse_id}, {len(gsms)} 个样本")
        return result
    except Exception as e:
        logger.error(f"下载失败: {e}")
        return {"success": False, "error": str(e), "gse_id": gse_id}


# ─────────────────────────────────────────────────────────────────────────────
# Tool: query_huggingface
# ─────────────────────────────────────────────────────────────────────────────

async def _query_huggingface(
    query: str,
    task: str = "",
    limit: int = 10,
    min_downloads: int = 0,
) -> dict[str, Any]:
    """搜索 HuggingFace Hub 上的生物信息模型。"""
    try:
        from huggingface_hub import HfApi
    except ImportError:
        return {"success": False, "error": "huggingface-hub 未安装：pip install huggingface-hub"}

    token = os.environ.get("HF_TOKEN")
    api = HfApi(token=token)

    logger.info(f"搜索 HuggingFace: query='{query}', task='{task}'")
    try:
        models = api.list_models(
            search=query,
            task=task if task else None,
            sort="downloads",
            direction=-1,
            limit=limit * 2,  # 多取一些，过滤后再截断
        )

        results = []
        for model in models:
            if min_downloads > 0 and (model.downloads or 0) < min_downloads:
                continue
            results.append({
                "model_id": model.modelId,
                "downloads": model.downloads,
                "likes": model.likes,
                "tags": model.tags[:10] if model.tags else [],
                "pipeline_tag": model.pipeline_tag,
                "last_modified": str(model.lastModified)[:10] if model.lastModified else None,
                "huggingface_url": f"https://huggingface.co/{model.modelId}",
            })
            if len(results) >= limit:
                break

        return {
            "success": True,
            "query": query,
            "total_found": len(results),
            "models": results,
            "note": (
                "请检查每个模型的许可证（CC-BY-NC 不可商业使用），"
                "并与 shared_memory/model_registry/ 中已有记录对比"
            ),
        }
    except Exception as e:
        logger.error(f"HuggingFace 搜索失败: {e}")
        return {"success": False, "error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# Tool: search_literature
# ─────────────────────────────────────────────────────────────────────────────

async def _search_literature(
    query: str,
    max_results: int = 10,
    email: str | None = None,
    database: str = "pubmed",
) -> dict[str, Any]:
    """通过 PubMed/Entrez API 搜索生物医学文献。"""
    try:
        from Bio import Entrez
    except ImportError:
        return {"success": False, "error": "biopython 未安装：pip install biopython"}

    email = email or os.environ.get("ENTREZ_EMAIL", "")
    if not email:
        return {
            "success": False,
            "error": "必须设置 ENTREZ_EMAIL 环境变量（NCBI 要求）",
        }

    Entrez.email = email
    api_key = os.environ.get("NCBI_API_KEY")
    if api_key:
        Entrez.api_key = api_key

    logger.info(f"搜索文献: '{query}' (db={database}, max={max_results})")
    try:
        # 搜索
        handle = Entrez.esearch(db=database, term=query, retmax=max_results)
        search_results = Entrez.read(handle)
        handle.close()

        pmids = search_results.get("IdList", [])
        if not pmids:
            return {"success": True, "query": query, "total_found": 0, "papers": []}

        # 获取摘要
        handle = Entrez.efetch(
            db=database, id=pmids, rettype="xml", retmode="xml"
        )
        records = Entrez.read(handle)
        handle.close()

        papers = []
        for record in records.get("PubmedArticle", []):
            try:
                article = record["MedlineCitation"]["Article"]
                pmid = str(record["MedlineCitation"]["PMID"])
                title = str(article.get("ArticleTitle", ""))
                abstract = ""
                if "Abstract" in article:
                    abstract_texts = article["Abstract"].get("AbstractText", [])
                    if isinstance(abstract_texts, list):
                        abstract = " ".join(str(t) for t in abstract_texts)
                    else:
                        abstract = str(abstract_texts)

                authors = []
                if "AuthorList" in article:
                    for author in article["AuthorList"][:3]:
                        last = author.get("LastName", "")
                        fore = author.get("ForeName", "")
                        if last:
                            authors.append(f"{last} {fore}".strip())

                pub_date = ""
                if "Journal" in article:
                    journal_issue = article["Journal"].get("JournalIssue", {})
                    pub_date_info = journal_issue.get("PubDate", {})
                    pub_date = pub_date_info.get("Year", "")

                papers.append({
                    "pmid": pmid,
                    "title": title,
                    "authors": authors,
                    "year": pub_date,
                    "abstract_snippet": abstract[:300] + "..." if len(abstract) > 300 else abstract,
                    "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                })
            except (KeyError, TypeError) as e:
                logger.debug(f"解析论文记录时出错: {e}")
                continue

        return {
            "success": True,
            "query": query,
            "database": database,
            "total_found": len(papers),
            "papers": papers,
        }
    except Exception as e:
        logger.error(f"文献搜索失败: {e}")
        return {"success": False, "error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# MCP Handler Registration
# ─────────────────────────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> ListToolsResult:
    return ListToolsResult(
        tools=[
            Tool(
                name="run_scanpy_qc",
                description=(
                    "对单细胞 RNA-seq 数据（.h5ad 格式）执行 Scanpy 质控。"
                    "过滤低质量细胞（基于最小基因数、最大线粒体比例）和低表达基因。"
                    "返回 QC 统计信息并输出过滤后的 .h5ad 文件。"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "input_path": {
                            "type": "string",
                            "description": "输入 .h5ad 文件路径（AnnData 格式）",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "输出 .h5ad 文件路径（QC 后）",
                        },
                        "min_genes": {
                            "type": "integer",
                            "description": "每个细胞最少检测到的基因数（默认 200）",
                            "default": 200,
                        },
                        "min_cells": {
                            "type": "integer",
                            "description": "每个基因最少在多少个细胞中表达（默认 3）",
                            "default": 3,
                        },
                        "mt_pct_threshold": {
                            "type": "number",
                            "description": "线粒体基因比例上限百分比（默认 20.0）",
                            "default": 20.0,
                        },
                    },
                    "required": ["input_path", "output_path"],
                },
            ),
            Tool(
                name="download_geo_data",
                description=(
                    "从 NCBI GEO（基因表达汇编）下载数据集。"
                    "使用 GEOparse 库，比直接 FTP 更稳定。"
                    "返回数据集元数据和下载路径。"
                    "注意：必须先设置 ENTREZ_EMAIL 环境变量。"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "gse_id": {
                            "type": "string",
                            "description": "GEO 系列 ID（如 'GSE123456'）",
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "下载目录路径",
                        },
                        "email": {
                            "type": "string",
                            "description": "NCBI 联系邮箱（可选，优先使用 ENTREZ_EMAIL 环境变量）",
                        },
                    },
                    "required": ["gse_id", "output_dir"],
                },
            ),
            Tool(
                name="query_huggingface",
                description=(
                    "搜索 HuggingFace Hub 上的生物信息基础模型。"
                    "支持按关键词、任务类型搜索，返回按下载量排序的模型列表。"
                    "Scout Agent 使用此工具发现新模型并更新注册表。"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索关键词（如 'single cell', 'scRNA', 'protein language model'）",
                        },
                        "task": {
                            "type": "string",
                            "description": "HuggingFace 任务类型（可选，如 'text-classification'）",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "返回结果数量上限（默认 10）",
                            "default": 10,
                        },
                        "min_downloads": {
                            "type": "integer",
                            "description": "最低下载量过滤（默认 0，不过滤）",
                            "default": 0,
                        },
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="search_literature",
                description=(
                    "通过 NCBI PubMed API 搜索生物医学文献。"
                    "返回标题、作者、摘要片段和 PubMed 链接。"
                    "Research Agent 使用此工具进行文献挖掘。"
                    "注意：必须先设置 ENTREZ_EMAIL 环境变量。"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "PubMed 搜索查询（支持布尔运算符，如 'scGPT AND single cell'）",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "返回结果数量上限（默认 10）",
                            "default": 10,
                        },
                        "email": {
                            "type": "string",
                            "description": "NCBI 联系邮箱（可选，优先使用 ENTREZ_EMAIL 环境变量）",
                        },
                        "database": {
                            "type": "string",
                            "description": "数据库（默认 'pubmed'，也支持 'pmc'）",
                            "default": "pubmed",
                        },
                    },
                    "required": ["query"],
                },
            ),
        ]
    )


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
    logger.info(f"调用工具: {name}, 参数: {json.dumps(arguments, ensure_ascii=False)[:200]}")

    if name == "run_scanpy_qc":
        result = await _run_scanpy_qc(**arguments)
    elif name == "download_geo_data":
        result = await _download_geo_data(**arguments)
    elif name == "query_huggingface":
        result = await _query_huggingface(**arguments)
    elif name == "search_literature":
        result = await _search_literature(**arguments)
    else:
        result = {"success": False, "error": f"未知工具: {name}"}

    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False, indent=2),
            )
        ]
    )


async def main() -> None:
    logger.info("BioOpenClaw MCP 服务器启动...")
    logger.info(f"项目根目录: {PROJECT_ROOT}")
    logger.info("可用工具: run_scanpy_qc, download_geo_data, query_huggingface, search_literature")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
