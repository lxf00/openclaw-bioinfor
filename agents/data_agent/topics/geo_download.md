# Topic: GEO 数据下载

> **关键词**: GEO, GEOparse, GSE, 数据下载, FTP, SRA, Aspera
> **写入者**: Data Agent
> **最后更新**: 2026-03-19

---

## 核心知识

### GEOparse 使用要点

- 首选 `GEOparse.get_GEO(geo=gse_id, how="brief")` 获取元数据
- `how="full"` 下载完整数据（含表达矩阵），文件可能很大
- 必须设置 `ENTREZ_EMAIL` 环境变量，否则 NCBI 会拒绝请求

### 数据格式注意

- GEO Series Matrix 文件通常已经 **log2 转换**，不要再做 log1p
- 补充文件（supplementary）可能是原始 counts（10x .mtx 格式或 .csv）
- 下载前通过 `gse.metadata` 检查 `type` 和 `summary` 判断数据格式

### 常见问题

| 问题 | 解决方案 |
|------|---------|
| FTP 下载超时 | 设置 retry（最多 3 次），或使用 Aspera（>5GB 文件） |
| NCBI 限流 | 使用 API key 提升到 10 req/s（无 key 限 3 req/s） |
| 系列矩阵 vs 原始数据 | 优先使用补充文件中的 raw counts |
| 多平台数据 | 通过 GPL ID 区分，不要混合不同平台的数据 |

### 最佳实践

1. 下载后立即计算 checksum 并记录到谱系文件
2. 使用 `inspect_dataset` 确认数据单位再做后续处理
3. 大文件（>5GB）建议先在非高峰时段下载
4. NCBI UTC 05:00-06:00 维护窗口避免下载
