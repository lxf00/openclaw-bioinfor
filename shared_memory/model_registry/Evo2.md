---
name: Evo2
version: "1.0"
updated: 2026-03-05
source: https://huggingface.co/arcinstitute/evo2_7b
paper: https://www.biorxiv.org/content/10.1101/2025.02.18.638918
license: Apache-2.0
parameters: 7B/40B
architecture: StripedHyena (SSM + Attention)
modalities: [DNA-sequence, RNA-sequence]
species: [multi-species, prokaryote, eukaryote]
---

# Evo2

## Available Variants

| 模型 | 参数量 | 上下文长度 | 推荐场景 |
|------|-------|-----------|---------|
| Evo2-7B | 7B | 8192 tokens | 常规基因组分析 |
| Evo2-40B | 40B | 8192 tokens | 最高精度需求 |

## Benchmarks
- [2026-03] Variant effect prediction: Spearman 0.52
- [2026-03] Genome generation quality: Alignment score>90%
- [2026-03] Cross-species generalization: AUROC=0.78

## Known Limitations
- 计算需求高：7B 版本需要 >=80GB VRAM（A100 80GB 或多卡）
- 上下文长度 8192 tokens（约 8kb 基因组序列）
- 对非编码区域的功能预测置信度低于编码区域

## Fine-tuning Notes
- 由于参数量大，强烈推荐 QLoRA（4-bit 量化）而非全参数微调
- 推荐 QLoRA: bits=4, rank=16, alpha=32
- Apache 2.0 许可证，可商业使用

## BioOpenClaw Usage History
<!-- Scout Agent 在此追加使用记录 -->
