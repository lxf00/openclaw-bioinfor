# BioOpenClaw Shared Memory Index

> **写入者**: `memory_consistency_check.py`（自动维护）+ 人类可手动编辑
> **加载时机**: Layer 1 — 每次会话启动时，所有 Agent 自动加载本文件
> **最后更新**: 2026-03-15

---

## Directory Routing

| 目录 | 内容 | 主写者 | 其他权限 |
|------|------|--------|---------|
| `model_registry/` | 生物信息基础模型注册表 | Scout Agent | 全员只读 |
| `literature/` | 文献知识库 | Research Agent | 全员只读 |
| `experiments/` | 实验记录（数据处理 + 模型微调 + 分析结果） | 全员 | 全员可追加 |
| `inbox/` | 跨实例消息投递（由调度脚本分发） | 全员 | 调度脚本路由 |
| `conventions.md` | 团队编码与文件约定（人类编写） | 人类 | 全员只读 |
| `known_issues.md` | 已知问题（任何 Agent 可追加） | 全员 | 全员可追加 |

---

## Quick Links

- 模型注册表总数: **4** （详见 `model_registry/_index.md`）
- 文献主题数: **0** （详见 `literature/_index.md`）
- 实验记录数: **0** （详见 `experiments/_index.md`）
- 已知问题: `known_issues.md`
- 团队约定: `conventions.md`

---

## Access Control Summary

### 写入权限矩阵（按 Agent）

| Agent | model_registry | literature | experiments | inbox | known_issues |
|-------|---------------|------------|-------------|-------|--------------|
| Scout Agent | **READ/WRITE** | READ | READ | WRITE | APPEND |
| Data Agent | READ | READ | **READ/WRITE** | WRITE | APPEND |
| Model Agent | READ | READ | **READ/WRITE** | WRITE | APPEND |
| Research Agent | READ | **READ/WRITE** | APPEND | WRITE | APPEND |
| Watcher | READ | READ | READ | WRITE | APPEND |

---

Last updated: 2026-03-15
