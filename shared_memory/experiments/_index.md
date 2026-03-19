# Experiments Index

> **写入权限**: 全员（Data Agent / Model Agent / Research Agent）
> **加载时机**: Layer 3（按需加载）
> **最后更新**: 2026-03-15

---

## 实验记录列表

| 日期 | 实验名称 | 类型 | 负责 Agent | 状态 | 详情 |
|------|---------|------|-----------|------|------|
| （待建立） | — | — | — | — | — |

---

## 实验类型分类

- **data_processing**: 数据下载、质控、批次校正
- **model_finetuning**: 模型微调实验
- **inference**: 推理部署验证
- **analysis**: 统计分析、假设检验

---

## 文件格式规范

```markdown
---
dataset: <GSE编号 或 TCGA项目名>
date: YYYY-MM-DD
processed_by: <agent_name>
experiment_type: data_processing | model_finetuning | inference | analysis
status: completed | failed | in_progress
---

# 实验名称

## 实验目的
## 配置与参数
## 结果摘要
## 输出文件路径
## 后续建议
```
