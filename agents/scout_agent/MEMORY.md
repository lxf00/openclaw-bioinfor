# Scout Agent Memory

> **写入者**: Scout Agent（仅本 Agent 可修改）
> **上限**: 200 行（超出由 memory_rotate.py 归档到 topics/）
> **Schema**: 仅允许以下三个 section，禁止新增

---

## Topic Routing

| 关键词 | 对应 Topic 文件 |
|--------|---------------|
| HuggingFace API, 搜索策略, Hub 访问 | `topics/huggingface_monitoring.md` |
| 基准测试, scIB, CASP, 性能追踪 | `topics/benchmark_tracking.md` |

---

## Core Lessons

<!-- 按日期降序排列，最新在前。格式：[YYYY-MM-DD] <教训内容> -->
- [2026-03-15] 初始化：Scout Agent 记忆系统建立，模型注册表预填了 ESM2/scGPT/Geneformer/Evo2 四个基础模型

---

## Active Warnings

<!-- 当前需要注意的短期警告，过期后移除 -->
- HuggingFace API 每分钟请求限制：未认证 100/min，认证用户 1000/min。生产环境必须设置 HF_TOKEN 环境变量
- 模型 License 需仔细核查：CC-BY-NC 不允许商业使用，注意区分 commercial / non-commercial
