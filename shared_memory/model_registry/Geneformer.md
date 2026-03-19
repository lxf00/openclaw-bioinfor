---
name: Geneformer
version: "1.0"
updated: 2026-03-08
source: https://huggingface.co/ctheodoris/Geneformer
paper: https://doi.org/10.1038/s41586-023-06139-9
license: CC-BY-NC-4.0
parameters: 10M
architecture: Transformer (BERT-style)
modalities: [scRNA-seq]
species: [human]
---

# Geneformer

## Benchmarks
- [2026-03] Cell type annotation: F1=0.89
- [2026-03] Gene network inference: AUROC=0.72
- [2026-03] Transcription factor prediction: AUROC=0.81

## Known Limitations
- **许可证限制**：CC-BY-NC，**不可用于商业场景**，使用前确认研究用途
- 仅支持人类基因组（不支持小鼠等其他物种）
- 需要将 raw counts 转换为 rank-value encoding（不同于标准 Scanpy 流程）
- 参数量较小（10M），复杂任务上可能不如 scGPT

## Fine-tuning Notes
- 使用 Geneformer 需要特殊的 rank-value encoding 预处理
- 推荐 LoRA rank=8, alpha=16, 学习率 2e-4
- 参考官方 fine-tuning notebook：`fine-tuning/` 目录

## BioOpenClaw Usage History
<!-- Scout Agent 在此追加使用记录 -->
