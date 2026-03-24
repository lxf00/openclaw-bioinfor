# LoRA 微调知识库

> **写入者**: Model Agent
> **最后更新**: 2026-03-15

---

## 推荐参数表

| 模型 | rank | alpha | 学习率 | target_modules | 备注 |
|------|------|-------|--------|---------------|------|
| scGPT | 8 | 16 | 2e-4 | query, value | 基因表达预测 |
| ESM2-650M | 16 | 32 | 1e-4 | query, key, value | 蛋白质任务 |
| Geneformer | 8 | 16 | 2e-4 | query, value | 细胞类型注释 |

## LoRA vs QLoRA 选择规则

- GPU 显存 >= 24GB → LoRA
- GPU 显存 < 24GB → QLoRA (4-bit)
- 模型参数 > 1B → 优先 QLoRA

## 常见问题

### Flash Attention

- ESM2 需要 `flash-attn>=2.0` 才能启用 Flash Attention
- scGPT 目前不支持 Flash Attention

### 训练不收敛

1. 降低学习率（÷10）
2. 增加 warmup ratio（0.1 → 0.2）
3. 检查数据是否正确预处理
