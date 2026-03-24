# Experiments Index

> **写入权限**: 全员（Data Agent / Model Agent / Research Agent）
> **加载时机**: Layer 3（按需加载）
> **最后更新**: 2026-03-21

---

## 实验记录列表

| 日期 | 实验名称 | 类型 | 负责 Agent | 状态 | 详情 |
|------|---------|------|-----------|------|------|
| 2026-03-19 | test_qc_pipeline | data_processing | data_agent | completed | `2026-03-19_test_qc_pipeline.md` |
| 2026-03-19 | test_multi_step | data_processing | data_agent | completed | `2026-03-19_test_multi_step.md` |
| 2026-03-19 | lineage_pipe | data_processing | data_agent | completed | `2026-03-19_lineage_pipe.md` |
| 2026-03-19 | experiment_record_test | data_processing | data_agent | completed | `2026-03-19_experiment_record_test.md` |
| 2026-03-19 | fail_test | data_processing | data_agent | failed | `2026-03-19_fail_test.md` |

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
