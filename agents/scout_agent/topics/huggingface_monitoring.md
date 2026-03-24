# HuggingFace 监控策略

> **写入者**: Scout Agent
> **最后更新**: 2026-03-15

---

## 搜索关键词（按优先级）

1. **单细胞基础模型**: `scRNA`, `single-cell`, `scGPT`, `Geneformer`
2. **蛋白质语言模型**: `protein`, `ESM`, `AlphaFold`
3. **基因组模型**: `genome`, `DNA`, `Nucleotide Transformer`, `Evo`
4. **空间转录组**: `spatial transcriptomics`, `Visium`

## 重点监控作者/组织

- `facebook` (Meta AI — ESM 系列)
- `bowang-lab` (scGPT)
- `ctheodoris` (Geneformer)
- `InstaDeepAI` (Nucleotide Transformer)

## API 使用注意事项

- 未认证：100 requests/min
- 认证用户：1000 requests/min
- 生产环境必须设置 `HF_TOKEN`

## 扫描频率建议

- 常规扫描：每日 1 次
- 重点领域：每 12 小时 1 次
