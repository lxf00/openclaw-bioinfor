# TCGA 数据下载经验

> **写入者**: Data Agent | **更新时间**: 2026-03-19

## GDC API 要点

- 端点: `https://api.gdc.cancer.gov/`
- 查询流程: files endpoint 查询 → 获取 file_id → data endpoint 下载
- 项目命名: `TCGA-BRCA`（乳腺癌）、`TCGA-LUAD`（肺腺癌）等
- 默认 workflow: `STAR - Counts`（推荐，raw counts）

## 常见陷阱

- TCGA 数据默认是 bulk RNA-seq，非单细胞
- `STAR - Counts` 输出为 raw counts（整数），`HTSeq - FPKM` 已经归一化
- 合并多个 TCGA 文件为 AnnData 时，基因列要取交集（`join="inner"`）
- 前 4 行通常是汇总行（`__no_feature`、`__ambiguous` 等），合并前需过滤

## 数据量参考

| 项目 | 样本数 | 说明 |
|------|--------|------|
| TCGA-BRCA | ~1,100 | 乳腺癌 |
| TCGA-LUAD | ~600 | 肺腺癌 |
| TCGA-LIHC | ~400 | 肝细胞癌 |
| TCGA-GBM | ~170 | 胶质母细胞瘤 |

## 与 GEO 数据的区别

- TCGA: 统一流程处理，标准化程度高，主要是 bulk RNA-seq
- GEO: 多样化，包含单细胞/bulk，处理流程各异
- 混合分析时注意 batch effect（不同平台、不同处理流程）
