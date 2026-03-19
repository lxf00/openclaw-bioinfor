# Model Agent Memory

> **写入者**: Model Agent（仅本 Agent 可修改）
> **上限**: 200 行（超出由 memory_rotate.py 归档到 topics/）
> **Schema**: 仅允许以下三个 section，禁止新增

---

## Topic Routing

| 关键词 | 对应 Topic 文件 |
|--------|---------------|
| LoRA, QLoRA, PEFT, 微调, rank, alpha | `topics/lora_finetuning.md` |
| Triton, vLLM, 推理, 部署, 服务 | `topics/triton_serving.md` |

---

## Core Lessons

<!-- 按日期降序排列，最新在前。格式：[YYYY-MM-DD] <教训内容> -->
- [2026-03-15] 初始化：Model Agent 记忆系统建立，LoRA 微调和推理服务框架已搭建
- [2026-03-15] scGPT LoRA 推荐参数：rank=8, alpha=16, lr=2e-4，全参数微调需要 >=24GB VRAM
- [2026-03-15] Flash Attention 2 可将 scGPT 训练速度提升约 40%，在支持的 GPU 上必须启用

---

## Active Warnings

<!-- 当前需要注意的短期警告，过期后移除 -->
- Geneformer 许可证为 CC-BY-NC，不可用于商业场景，使用前确认研究用途
- vLLM 与 Triton 的接口版本需对齐，升级前检查兼容性矩阵
