# Model Registry Index

> **写入者**: Scout Agent（唯一写入者）
> **加载时机**: Layer 3（按需加载）
> **最后扫描**: 2026-03-15

---

## Registered Models

| 模型 | 版本 | 类型 | 参数量 | 许可证 | 更新日期 | 详情 |
|------|------|------|-------|--------|---------|------|
| ESM2 | 3B/650M/150M/35M | 蛋白质语言模型 | 35M–3B | MIT | 2026-03-12 | [ESM2.md](ESM2.md) |
| scGPT | 2.0 | 单细胞基础模型 | 51.3M | MIT | 2026-03-10 | [scGPT.md](scGPT.md) |
| Geneformer | 1.0 | 单细胞基础模型 | 10M | CC-BY-NC | 2026-03-08 | [Geneformer.md](Geneformer.md) |
| Evo2 | 1.0 | DNA 基础模型 | 7B/40B | Apache 2.0 | 2026-03-05 | [Evo2.md](Evo2.md) |

---

## Statistics

- **Total models**: 4
- **Last scan**: 2026-03-15
- **Next scheduled scan**: 2026-03-22（每周一次）

---

## Coverage Gaps

- 蛋白质结构预测模型（OpenFold3、RoseTTAFold2 等）尚未注册
- 药物分子生成模型（REINVENT4、DiffSBDD 等）尚未注册
- 多组学整合模型尚未系统评估
- 空间转录组特化模型（BANKSY、Tangram 等）尚未注册

---

## Modality Coverage

| 模态 | 覆盖模型 |
|------|---------|
| scRNA-seq | scGPT, Geneformer |
| 蛋白质序列 | ESM2 |
| DNA 序列 | Evo2 |
| CITE-seq | scGPT |
| 空间转录组 | scGPT（部分） |
