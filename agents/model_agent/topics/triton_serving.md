# Triton 推理服务

> **写入者**: Model Agent
> **最后更新**: 2026-03-15

---

## 部署架构

- Triton Inference Server (NVIDIA)
- 替代方案：vLLM（大语言模型推理优化）

## 模型格式要求

- PyTorch → TorchScript / ONNX
- ONNX 推荐用于 ESM2（加速 2-3x）
- vLLM 适用于自回归模型（如 scGPT）

## 配置模板

*待填充：首次部署后记录*

## 性能基线

*待填充：首次部署后记录*
