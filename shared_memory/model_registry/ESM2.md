---
name: ESM2
version: "3B/650M/150M/35M"
updated: 2026-03-12
source: https://huggingface.co/facebook/esm2_t36_3B_UR50D
paper: https://doi.org/10.1126/science.ade2574
license: MIT
parameters: 35M-3B
architecture: Transformer (ESM architecture)
modalities: [protein-sequence]
species: [multi-species]
---

# ESM2

## Available Variants

| 模型 | 参数量 | 推荐场景 |
|------|-------|---------|
| ESM2-3B | 3B | 最高精度需求 |
| ESM2-650M | 650M | 平衡精度与速度 |
| ESM2-150M | 150M | 快速原型 |
| ESM2-35M | 35M | 资源受限场景 |

## Benchmarks
- [2026-03] ProteinGym substitution DMS: Spearman 0.47 (3B)
- [2026-03] Secondary structure prediction: Q3=0.89 (3B)
- [2026-03] Protein-protein interaction: AUROC=0.83 (650M)

## Known Limitations
- 不能处理修饰氨基酸（如磷酸化位点）
- 序列长度上限 1022 个氨基酸（超长蛋白需分段）
- 对 intrinsically disordered regions (IDR) 的预测置信度低

## Fine-tuning Notes
- 推荐 LoRA rank=16, alpha=32, 学习率 1e-4
- 650M 版本在单张 A100 40GB 上可全参数微调
- 使用 ESMFold 时注意额外的结构预测内存开销

## BioOpenClaw Usage History
<!-- Scout Agent 在此追加使用记录 -->
