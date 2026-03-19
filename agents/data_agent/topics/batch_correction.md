# Topic: 批次校正

> **关键词**: 批次校正, Harmony, scVI, Combat, 批次效应, kBET, LISI
> **写入者**: Data Agent
> **最后更新**: 2026-03-19

---

## 核心知识

### 方法选择决策树

```
batch 数量 == 1 → 跳过批次校正
batch 数量 <= 3 → Harmony（快速，嵌入空间校正）
batch 数量 > 3  → scVI（深度学习，更强校正力）
技术批次 + 需要 DE → Combat（直接修正表达矩阵）
```

### 方法对比

| 方法 | 速度 | 校正力 | 修改对象 | 依赖 |
|------|------|--------|---------|------|
| Harmony | 快 | 中 | PCA 嵌入 (obsm) | harmonypy |
| scVI | 慢 | 强 | 潜在空间 (obsm) | scvi-tools (GPU 推荐) |
| Combat | 中 | 中 | 表达矩阵 (X) | scanpy 内置 |

### 前置条件

1. `batch_key` 必须存在于 `adata.obs` 中
2. 数据需已经过 QC 和归一化
3. PCA 需已运行（如未运行，工具会自动运行）

### 质量评估指标

- **kBET**: acceptance rate > 0.8 表示批次混合良好
- **LISI**: batch LISI 越高越好（接近 batch 数量），cell type LISI 越低越好（接近 1）
- **UMAP**: 校正后不同批次的细胞应混合均匀

### 注意事项

- Harmony 只修改嵌入空间，不改变表达矩阵，适合聚类和可视化
- Combat 直接修改表达矩阵，适合差异表达分析
- scVI 需要 GPU 支持以获得合理训练时间（>10 万细胞）
- 校正过度会消除真实的生物学差异，需要在校正力和保真度之间权衡
