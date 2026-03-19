# Research Agent Memory

> **写入者**: Research Agent（仅本 Agent 可修改）
> **上限**: 200 行（超出由 memory_rotate.py 归档到 topics/）
> **Schema**: 仅允许以下三个 section，禁止新增

---

## Topic Routing

| 关键词 | 对应 Topic 文件 |
|--------|---------------|
| 假设生成, 假设框架, 科学假设, H0, H1 | `topics/hypothesis_generation.md` |
| 统计检验, p值, 多重校正, FDR, Bonferroni | `topics/statistical_testing.md` |

---

## Core Lessons

<!-- 按日期降序排列，最新在前。格式：[YYYY-MM-DD] <教训内容> -->
- [2026-03-15] 初始化：Research Agent 记忆系统建立，文献检索和假设生成框架已搭建
- [2026-03-15] PubMed API 需要设置 ENTREZ_EMAIL，否则查询限制为 3 requests/second（设置后提升到 10/s）
- [2026-03-15] 单细胞分析的多重检验校正必须使用 BH-FDR（Benjamini-Hochberg），而非 Bonferroni（过于保守，假阴性率高）

---

## Active Warnings

<!-- 当前需要注意的短期警告，过期后移除 -->
- arXiv API 限速：100 requests/5min，批量检索时注意控制频率
- 预印本（bioRxiv/medRxiv）结果未经同行评审，引用时注意区分，不应直接作为临床决策依据
