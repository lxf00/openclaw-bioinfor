# 基准测试追踪

> **写入者**: Scout Agent
> **最后更新**: 2026-03-15

---

## 关注的基准测试

### 单细胞领域

- **scIB**: 单细胞整合基准 (batch correction, cell type annotation)
- **scPerturb**: 扰动响应预测基准

### 蛋白质领域

- **CASP**: 蛋白质结构预测竞赛
- **TAPE**: 蛋白质工程任务基准
- **ProteinGym**: 蛋白质适应性预测

### 基因组领域

- **Nucleotide Transformer Benchmarks**: 基因组变异预测
- **GeneBench**: 基因表达预测

## 性能追踪规则

- 新基准测试结果发布后 48 小时内更新 model_registry
- 性能显著下降（> 5%）时通知 Model Agent
