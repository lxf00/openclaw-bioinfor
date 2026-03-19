---
name: scGPT
version: "2.0"
updated: 2026-03-10
source: https://huggingface.co/bowang-lab/scGPT
paper: https://doi.org/10.1038/s41592-024-02201-0
license: MIT
parameters: 51.3M
architecture: Transformer
modalities: [scRNA-seq, spatial, CITE-seq]
species: [human, mouse]
---

# scGPT

## Benchmarks
- [2026-03] scIB batch integration: 0.82
- [2026-03] Cell type annotation (Immune Human): F1=0.94
- [2026-02] Gene perturbation prediction: Pearson r=0.71

## Known Limitations
- 对稀有细胞类型（<1% 占比）的标注准确率显著下降
- Spatial 模态需要 >=300 genes/spot
- 跨物种迁移（human → mouse）性能下降约 15%

## Fine-tuning Notes
- 推荐 LoRA rank=8, alpha=16, 学习率 2e-4
- 全参数微调需要 >=24GB VRAM（A100 推荐）
- Flash Attention 2 可将训练速度提升约 40%

## BioOpenClaw Usage History
<!-- Scout Agent 在此追加使用记录 -->
