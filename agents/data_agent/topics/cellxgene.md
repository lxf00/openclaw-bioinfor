# CellxGene Census 使用经验

> **写入者**: Data Agent | **更新时间**: 2026-03-19

## 概览

- CZ CellxGene Census 托管 1.6 亿+ 单细胞数据，1500+ 数据集
- 底层存储引擎: TileDB-SOMA
- REST API: `https://api.cellxgene.cziscience.com/curation/v1/`
- Python SDK: `cellxgene-census` + `tiledbsoma`

## 两种查询模式

### 元数据查询（轻量，无需 SDK）
- 使用 REST API `/collections` 端点
- 按组织、疾病、细胞类型、物种过滤
- 返回 collection 级别元数据（标题、数据集数、细胞总数）

### 表达数据下载（需要 SDK）
- `cellxgene-census` 库必须安装
- 通过 `obs_value_filter` 过滤（TileDB 查询语法）
- 直接返回 AnnData 对象
- 大数据量时设置 `max_cells` 限制

## 常见陷阱

- Census 数据已经过标准化处理（counts 矩阵 + 标准化 obs 列名）
- 查询超时时缩小 `obs_filter` 范围，而非增加 timeout
- `organism` 参数用 `homo_sapiens` / `mus_musculus`（下划线格式）
- Census 版本会定期更新，同一查询可能返回不同数据量

## obs 标准列名

常用的 obs 列: `cell_type`, `tissue`, `disease`, `assay`, `donor_id`, `sex`, `development_stage`

## 与 GEO 的互补性

- GEO: 原始数据，需自行处理
- CellxGene: 已处理数据，标准化 obs 列名，适合快速获取高质量数据
- 建议：先在 CellxGene 搜索，如果没有再到 GEO
