# 统计检验指南

> **写入者**: Research Agent
> **最后更新**: 2026-03-15

---

## 检验选择决策树

1. **数据类型？**
   - 连续型 → 2
   - 分类型 → Chi-squared / Fisher's exact

2. **正态分布？**（Shapiro-Wilk 检验）
   - 正态 → 参数检验 → 3
   - 非正态 → 非参数检验 → 4

3. **参数检验**
   - 2 组独立 → Student's t-test (or Welch's)
   - 2 组配对 → Paired t-test
   - >2 组 → ANOVA + post-hoc (Tukey/Bonferroni)

4. **非参数检验**
   - 2 组独立 → Mann-Whitney U
   - 2 组配对 → Wilcoxon signed-rank
   - >2 组 → Kruskal-Wallis + Dunn's test

## 多重检验校正

- **Bonferroni**：保守，适用于少量检验（<20）
- **BH-FDR**：推荐，适用于大量检验（>20，如基因组学）
- **规则**：≥2 个检验时必须校正

## 效应量报告

| 检验 | 效应量指标 | 小/中/大 |
|------|-----------|---------|
| t-test | Cohen's d | 0.2/0.5/0.8 |
| Mann-Whitney | r | 0.1/0.3/0.5 |
| Chi-squared | Cramér's V | 0.1/0.3/0.5 |

## PubMed API 注意事项

- NCBI 要求设置 ENTREZ_EMAIL
- 有 API key 时请求限制 10/sec，无 key 时 3/sec
- 使用 BH-FDR 而非 Bonferroni 做多重校正（生物信息学惯例）
