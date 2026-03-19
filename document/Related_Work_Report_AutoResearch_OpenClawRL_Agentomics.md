# 相关工作调研报告：AutoResearch、OpenClaw-RL、Agentomics

> **版本**: v1.0 | **日期**: 2026-03-15
> **目的**: 系统分析三个代表性项目，提炼对 BioOpenClaw 的设计启示

---

## 目录

1. [概述与选择理由](#一概述与选择理由)
2. [AutoResearch：极简 Agent 训练循环](#二autoresearch极简-agent-训练循环)
3. [OpenClaw-RL：对话驱动的在线强化学习](#三openclaw-rl对话驱动的在线强化学习)
4. [Agentomics：生物医学自动化 ML 实验](#四agentomics生物医学自动化-ml-实验)
5. [三项工作的横向对比](#五三项工作的横向对比)
6. [对 BioOpenClaw 的综合启示](#六对-bioopenclaw-的综合启示)
7. [推荐的 Phase 2 行动项](#七推荐的-phase-2-行动项)

---

## 一、概述与选择理由

BioOpenClaw 是一个多 OpenClaw 实例的多 AI 生物信息科学家群框架，五个 Agent（Scout、Data、Model、Research、Watcher）分工协作完成生信全链路工作。当前处于 Phase 1 MVP 阶段（MCP 桥接验证）。

本报告选择以下三个项目进行深入分析，原因如下：

- **AutoResearch**（Karpathy, 2026.03）：展示了用编程 Agent 自动化模型训练的极简范式，与 BioOpenClaw Model Agent 的训练自动化目标最直接相关
- **OpenClaw-RL**（Gen-Verse, 2026.03）：作为 OpenClaw 框架的官方 RL 训练扩展，与 BioOpenClaw 共享技术栈，可直接集成
- **Agentomics**（BioGeMT, 2026.01）：唯一在生物医学领域达到 SOTA 的自动化 ML Agent 系统，领域知识高度重叠

---

## 二、AutoResearch：极简 Agent 训练循环

### 2.1 基本信息

| 属性 | 内容 |
|------|------|
| **作者** | Andrej Karpathy |
| **发布时间** | 2026年3月 |
| **代码** | https://github.com/karpathy/autoresearch |
| **GitHub Stars** | 35,000+ |
| **代码量** | 630行 Python |
| **许可证** | MIT |

### 2.2 核心思想

AutoResearch 的核心理念是：**让 AI Agent 在一个受控的训练循环中自主进行 ML 实验研究**。Agent 在循环中不断修改训练代码、执行短时训练、评估指标，然后决定保留改进或回滚失败尝试——整个过程无需人类干预，可以过夜运行 100+ 次实验。

### 2.3 架构设计

AutoResearch 采用极简的**三文件架构**：

```
autoresearch/
├── program.md    ← 人类编写的研究策略和约束（只读）
├── train.py      ← Agent 可自由修改的训练脚本（可写）
└── prepare.py    ← 数据准备和评估代码（只读，信任边界）
```

**信任边界分离**是核心设计原则：
- `program.md`：定义研究目标、允许/禁止的操作、评估标准。Agent 只能读取，不能修改
- `train.py`：包含 GPT 模型定义、优化器配置、训练循环（约 630 行），是 Agent 唯一的修改目标
- `prepare.py`：数据准备和验证评估的固定代码，Agent 不可触碰，确保评估公正性

### 2.4 训练循环

```
┌──────────────────────────────────────────────────────┐
│                 AutoResearch 循环                      │
│                                                        │
│  1. Agent 读取 program.md（获取策略指导）                │
│  2. Agent 读取当前 train.py（理解现有代码）               │
│  3. Agent 提出代码修改方案                               │
│  4. 提交修改，执行 git commit                            │
│  5. 运行训练，固定 5 分钟时间窗口                         │
│  6. 评估 validation bits-per-byte (val_bpb)             │
│  7. 如果指标改进 → 保留 commit                           │
│     如果指标没有改进 → git reset 回滚                     │
│  8. 记录结果到 results.tsv                               │
│  9. 回到步骤 1，永不停止                                  │
└──────────────────────────────────────────────────────┘
```

**关键设计决策**：
- **固定 5 分钟训练窗口**：所有实验在同一时间预算下进行，确保可比性
- **Git 作为记忆系统**：Agent 通过 git log 和 results.tsv 回顾历史实验，决定下一步策略
- **永不停止指令**：Agent 被明确要求在循环中持续运行，不停下来询问人类
- **Claude 作为首选后端**：Claude 能可靠遵守"永不停止"指令，其他模型（如 OpenAI Codex）会忽略此约束

### 2.5 实际效果

| 指标 | 数值 |
|------|------|
| 单次运行实验数 | 89-126 次 |
| 运行时间 | 7.5 小时（过夜） |
| val_bpb 改进 | 0.9979 → 0.9697 (约 2.8%) |
| 有效改进比例 | 15/89 保留 (16.9%) |
| 硬件需求 | 单张 NVIDIA H100 |
| LLM API 费用 | 约 $50-200/晚 |

Agent 发现的改进包括：
- 缺失的 scaler 乘数因子（真实 bug）
- 优化器参数配置错误
- 次优的 weight decay 调度策略
- 学习率调度改进

### 2.6 对 BioOpenClaw 的启示

#### 启示 1：信任边界三文件架构可直接复用

BioOpenClaw Model Agent 可以采用类似的三文件架构进行生信模型训练：

| AutoResearch 文件 | BioOpenClaw 对应 | 说明 |
|-------------------|-----------------|------|
| `program.md` | `training_strategy.md` | 定义训练目标、约束条件、允许的超参范围 |
| `train.py` | `lora_train.py` | Agent 可修改的 LoRA 微调训练脚本 |
| `prepare.py` | `eval_pipeline.py` | 锁定的数据加载和评估代码（信任边界） |

这种分离确保 Agent 无法篡改评估标准或泄露测试集。

#### 启示 2：Git 作为轻量级实验记忆

AutoResearch 用 git 作为记忆系统的设计与 BioOpenClaw 的三层记忆架构高度互补：
- **Layer 1**（MEMORY.md）可存储跨会话的最佳超参发现
- **Layer 2**（active_context.md）可记录当前训练会话的中间状态
- **Layer 3**（shared_memory/experiments/）可存储详细的实验日志
- **Git history** 本身可作为第四层"训练考古"记录

#### 启示 3：固定时间预算确保可比性

在生信模型训练中，不同模型/超参的训练时间差异巨大。采用固定时间窗口（如 10 分钟 LoRA 微调）可以让 Agent 在公平条件下比较不同策略的效果。

#### 启示 4：成本可控的自主探索

AutoResearch 证明了 Agent 自主训练的 API 费用在可接受范围内（$50-200/晚）。BioOpenClaw 可以设置预算上限，在成本约束下最大化实验数量。

---

## 三、OpenClaw-RL：对话驱动的在线强化学习

### 3.1 基本信息

| 属性 | 内容 |
|------|------|
| **作者** | Yinjie Wang, Xuyang Chen, Xiaolong Jin, Mengdi Wang, Ling Yang (Gen-Verse) |
| **论文** | arXiv:2603.10165 |
| **发布时间** | 2026年3月10日 |
| **代码** | https://github.com/Gen-Verse/OpenClaw-RL |
| **GitHub Stars** | 2,775 |
| **基础框架** | OpenClaw + slime (异步 RL 基础设施) |
| **状态** | HuggingFace Daily Papers #1 |

### 3.2 核心思想

OpenClaw-RL 的核心洞察是：**每一次 Agent 交互都会产生一个"下一状态信号"（next-state signal），这些信号是免费的训练数据来源，却被现有系统浪费了。** 该框架将用户回复、工具输出、终端状态变化等统一回收为两种形式的训练信号：

1. **评估性信号（Evaluative signals）**：表示 Agent 动作的好坏，通过 PRM（Process Reward Model）转化为标量奖励
2. **指导性信号（Directive signals）**：表示 Agent 动作应该如何改变，通过 Hindsight-Guided On-Policy Distillation (OPD) 提取为 token 级别的监督信号

### 3.3 架构设计

OpenClaw-RL 采用**全异步四组件架构**，构建在 slime 框架之上：

```
┌─────────────────────────────────────────────────────────────┐
│                    OpenClaw-RL 架构                           │
│                                                               │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌─────────┐ │
│  │ SGLang   │    │Environment│    │ PRM/Judge│    │Megatron │ │
│  │ (推理)   │───▶│ Server   │───▶│ (奖励)   │───▶│ (训练)  │ │
│  │          │◀───│          │    │          │    │         │ │
│  └──────────┘    └──────────┘    └──────────┘    └─────────┘ │
│       ▲                                              │        │
│       └──────────── 权重更新（非阻塞）────────────────┘        │
│                                                               │
│  关键特性：四个组件完全解耦，异步运行，零协调开销                  │
└─────────────────────────────────────────────────────────────┘
```

**四个独立组件**：
- **SGLang（Policy Serving）**：通过 OpenAI 兼容 API 提供推理服务，支持 graceful weight update
- **Environment Server**：处理 Agent 与环境的交互，支持个人 Agent（用户设备）和通用 Agent（云端）
- **PRM / Judge**：基于下一状态信号评估 Agent 动作质量，支持多次投票取多数
- **Megatron（Policy Training）**：执行策略梯度更新，不阻塞推理和评估

### 3.4 两种训练方法

#### 方法 1：Binary RL（评估性信号回收）

将下一状态信号转化为标量过程奖励：
- PRM 评估每个 Agent 动作，给出 +1（好）、-1（差）、0（中性）
- 采用 PPO 风格的裁剪代理目标进行训练
- 适用于所有交互类型，包括隐式反馈（用户重新提问表示不满意）

#### 方法 2：Hindsight-Guided OPD（指导性信号回收）

将指导性下一状态信号转化为 token 级别的监督：
1. **提示提取**：从下一状态中提取可操作的纠正提示（1-3 句）
2. **增强上下文构建**：将提示附加到原始输入，构造"如果用户提前给出纠正"的增强上下文
3. **Token 级别优势计算**：比较增强上下文下的 token 概率与原始概率的差异
4. **有选择的训练**：仅对高质量提示（>10 字符）的样本进行训练

**两种方法的互补性**：Binary RL 覆盖所有 turn，提供广泛但粗粒度的梯度；OPD 仅覆盖有明确纠正的 turn，但提供精细的 token 级别指导。

### 3.5 支持的场景

| 场景 | 环境 | 下一状态信号 | 时间跨度 |
|------|------|-------------|---------|
| OpenClaw 个人 Agent | 用户设备 | 用户回复 / 工具调用结果 | 长 |
| 终端 Agent | Shell 沙盒 | stdout/stderr, 退出码 | 长 |
| GUI Agent | 屏幕状态 + 可达性树 | 视觉状态差异, 任务进度 | 长 |
| SWE Agent | 代码仓库 + 测试套件 | 测试结果, diff, lint 输出 | 长 |
| 工具调用 Agent | API/函数执行 | 返回值, 错误跟踪 | 中等 |

### 3.6 实验结果

**个人 Agent 个性化**（模型：Qwen3-4B）：

| 方法 | 8 步更新后 | 16 步更新后 |
|------|-----------|-----------|
| Binary RL | 0.25 | 0.23 |
| OPD | 0.25 | 0.72 |
| Combined | 0.76 | 0.81 |

**通用 Agent RL**（步进奖励 vs 结果奖励）：

| 场景 | 集成奖励 | 仅结果奖励 |
|------|---------|-----------|
| 工具调用 | 0.30 | 0.17 |
| GUI | 0.33 | 0.31 |

### 3.7 对 BioOpenClaw 的启示

#### 启示 1：Agent 可通过使用自身来持续改进

OpenClaw-RL 最革命性的贡献是证明了 Agent 可以"通过被使用来变好"。对于 BioOpenClaw：
- **Scout Agent** 每次搜索 HuggingFace 后，用户的后续操作（是否采纳推荐的模型）就是评估信号
- **Data Agent** 每次执行 QC 后，Watcher 的反馈就是评估信号
- **Model Agent** 每次微调后的验证指标就是最直接的评估信号

这意味着 BioOpenClaw 五个 Agent 在正常工作中产生的所有交互数据，都可以作为训练信号回收。

#### 启示 2：异步架构适合长时训练任务

生信模型训练（LoRA 微调 scGPT/Geneformer）通常需要数小时。OpenClaw-RL 的异步设计确保训练不阻塞推理——Model Agent 可以在微调运行期间继续处理其他请求。这直接解决了 BioOpenClaw 的核心工程挑战。

#### 启示 3：Watcher 纠偏可作为 OPD 的指导性信号

BioOpenClaw 的 Watcher Agent 产生的纠偏指令（如"Model Agent 应该先检查数据质量再开始训练"）是完美的 OPD 指导性信号来源。当前 Watcher 仅将纠偏写入 inbox，未来可以直接作为 OPD 训练信号回收。

#### 启示 4：会话感知的训练数据分类

OpenClaw-RL 区分"主线 turn"（可训练）和"辅助 turn"（不训练），这对 BioOpenClaw 很重要：
- **主线 turn**：Agent 执行核心任务（训练、评估、数据下载）
- **辅助 turn**：Agent 组织记忆、查询索引、更新状态文件
- 仅对主线 turn 生成训练样本，避免污染策略

#### 启示 5：LoRA 训练支持可直接集成

OpenClaw-RL 在 2026 年 3 月的更新中已经添加了 LoRA 训练支持和混合部署（本地 GPU + 云端），这与 BioOpenClaw Model Agent 的 LoRA/QLoRA 微调需求完美匹配。

---

## 四、Agentomics：生物医学自动化 ML 实验

### 4.1 基本信息

| 属性 | 内容 |
|------|------|
| **作者** | Panagiotis Alexiou 等 11 人 (University of Malta, BioGeMT) |
| **论文** | bioRxiv 2026.01.27.702049 |
| **发布时间** | 2026年1月27日 |
| **代码** | https://github.com/BioGeMT/Agentomics-ML |
| **LLM 后端** | GPT-5.1-Codex-Max（推荐） |
| **许可证** | Creative Commons CC BY 4.0 |
| **领域** | 蛋白质工程、药物发现、调控基因组学 |

### 4.2 核心思想

Agentomics 是第一个在生物医学基准数据集上系统性超越人类专家的自动化 ML Agent 系统。其核心理念是：**将 ML 实验分解为预定义的验证步骤序列，每个步骤由独立的 LLM Agent 执行，并经过严格的结构化和功能性验证后才进入下一步。**

### 4.3 架构设计

#### 4.3.1 预定义步骤序列

Agentomics 将一次 ML 实验（一个 iteration）分解为 7 个预定义步骤，从下到上执行：

```
Step 7: Data Exploration        ← 探索数据，输出描述统计
Step 6: Data Splitting          ← 分割训练/验证集
Step 5: Data Representation     ← 决定数据表示方式
Step 4: Model Architecture      ← 决定模型架构和超参
Step 3: Training                ← 实现训练脚本，执行训练
Step 2: Inference               ← 实现推理脚本
Step 1: Prediction Exploration  ← 分析预测结果，识别偏差
```

每个步骤的关键特性：
- **独立 LLM 上下文**：每步启动新的 LLM Agent，注入基础 prompt + 前序步骤的结构化输出
- **结构化验证**：输出必须通过 JSON 格式验证
- **功能性验证**：输出必须通过步骤特定的程序化检查（如推理脚本必须能在不同数据子集上运行）
- **重试机制**：验证失败时 Agent 收到错误信息并重试，超过重试限制则从头开始

#### 4.3.2 迭代实验设计

```
┌───────────────────────────────────────────────────────────────┐
│                    Agentomics 迭代流程                          │
│                                                                 │
│  Iteration 1:                                                   │
│    7 个步骤 → 产出模型 M1 → 计算 train/val 指标 → Iteration   │
│    Summary 1                                                    │
│                                                                 │
│  Iteration 2:                                                   │
│    Experiment Design LLM 读取所有历史 Iteration Summaries       │
│    → 生成新的步骤指令 → 7 个步骤 → 产出模型 M2 → ...           │
│                                                                 │
│  ...（重复直到时间/迭代限制）                                     │
│                                                                 │
│  输出：选择验证集最佳得分的 Iteration 的全部产物                   │
│    - 训练脚本（可重训练）                                        │
│    - 推理脚本（可预测新数据）                                     │
│    - 模型权重和 artifacts                                        │
│    - PDF 报告                                                    │
│    - Conda 环境                                                  │
└───────────────────────────────────────────────────────────────┘
```

#### 4.3.3 工具系统

Agentomics 提供 6 个工具：

1. **final_result**：返回步骤结构化输出（JSON）
2. **foundation_models_info**：查询可用基础模型的文档和代码片段
3. **edit**：编辑现有文件
4. **python_run**：执行 Python 文件并返回控制台输出
5. **python_write**：语法检查后写入 Python 文件
6. **bash**：运行 bash 命令，安装包

#### 4.3.4 预置基础模型

| 领域 | 模型 | 数量 |
|------|------|------|
| 蛋白质序列 | ESM-2 | 6 个变体 |
| DNA 序列 | HyenaDNA | 5 个变体 |
| DNA 序列 | NucleotideTransformer | 9 个变体 |
| RNA 序列 | RiNALMo | 3 个变体 |
| 小分子 | ChemBERTa | 7 个变体 |
| 小分子 | MolFormerXL | 1 个变体 |

Agent 可通过 `foundation_models_info` 工具检索每个模型的文档和使用代码片段。

### 4.4 安全与隔离

- **Docker 容器化**：所有实验在隔离的 Docker 容器中运行，只读挂载防止修改宿主系统
- **测试集严格隔离**：测试集在整个运行期间对所有 Agent 完全不可见
- **指标由确定性代码计算**：不依赖 Agent 自报指标，防止指标幻觉
- **本地 LLM 支持**：支持本地部署的开源 LLM，解决敏感生物医学数据的隐私问题

### 4.5 实验结果

#### 4.5.1 总体成绩

- **20 个基准数据集**中在 **11 个达到新的 SOTA**（超越人类专家工程化模型）
- **蛋白质工程**：6/6 数据集超越人类 SOTA
- **调控基因组学**：4/5 数据集匹配或超越人类 SOTA
- **药物发现**：2/9 数据集达到新 SOTA

#### 4.5.2 运行成本与效率

| 指标 | 数值 |
|------|------|
| 平均单次运行费用 | $9.4 ± $5.0 |
| 单个 Iteration 费用 | $0.45 ± $0.09 |
| 单个 Iteration 时长 | ~30 分钟 |
| 成功率 | 100%（60 次运行全部产出可用模型） |
| 硬件 | NVIDIA RTX A4000 + 48 CPU cores |
| 运行时长 | 8 小时 |

#### 4.5.3 策略多样性

Agentomics 在 364 个 Iteration 中探索了广泛的策略类型：
- 传统方法：线性回归、SVM、随机森林
- 深度学习：Transformer、CNN、混合架构
- 集成方法：XGBoost、随机森林集成、自定义集成
- 基础模型：20% 的最终产出使用了基础模型嵌入

#### 4.5.4 案例研究：AGO2 CLASH 数据集

Agent 从逻辑回归基线开始，逐步尝试：
1. 梯度提升树
2. 标准 CNN 和 Transformer
3. Watson-Crick 碱基配对交互矩阵（与已知 miRNA-靶标生物学一致）
4. 微调 Nucleotide Transformer（~50M 参数）
5. 交叉注意力双编码器
6. CNN 集成（残差、深度可分、ConvNeXt 风格）
7. 最终方案：5 个集成的概率加权组合

最终 AUPRC 0.880 vs 人类 SOTA 0.860。

### 4.6 对 BioOpenClaw 的启示

#### 启示 1：预定义步骤 + 验证检查点的流水线设计

Agentomics 的 7 步流水线设计可以直接启发 BioOpenClaw Model Agent 的训练流程：

| Agentomics 步骤 | BioOpenClaw 对应 | 负责 Agent |
|-----------------|-----------------|-----------|
| Data Exploration | 数据质量检查 | Data Agent |
| Data Splitting | 训练/验证集分割 | Data Agent |
| Data Representation | 特征工程/嵌入选择 | Model Agent + Research Agent |
| Model Architecture | 模型架构和超参决策 | Model Agent |
| Training | LoRA/QLoRA 微调执行 | Model Agent |
| Inference | 推理脚本生成 | Model Agent |
| Prediction Exploration | 预测偏差分析 | Research Agent |

**关键差异**：BioOpenClaw 可以利用多 Agent 协作将 Agentomics 的单 Agent 多步流水线升级为多 Agent 并行流水线——Data Agent 做数据准备的同时，Research Agent 可以查阅文献确定最佳数据表示方法。

#### 启示 2：基础模型信息工具至关重要

Agentomics 的 `foundation_models_info` 工具让 Agent 能查询每个基础模型的文档和代码片段，这是 Agent 有效使用 ESM-2、scGPT 等模型的前提。

BioOpenClaw 应在 `shared_memory/model_registry/` 中为每个生信基础模型维护结构化信息：
- 模型参数量和架构
- 支持的输入格式（序列、表达矩阵等）
- 微调代码模板（LoRA config, 数据加载器）
- 已知的最佳实践和陷阱
- 基准性能参考

目前 `shared_memory/model_registry/` 已有 ESM2.md、scGPT.md、Geneformer.md、Evo2.md 的索引条目，但需要补充代码片段和微调模板。

#### 启示 3：Docker 容器化确保可复现性和安全性

Agentomics 的全容器化设计解决了三个关键问题：
- **安全性**：防止 Agent 生成的代码损害宿主系统
- **可复现性**：固定环境确保实验可重复
- **隔离性**：不同实验之间互不干扰

BioOpenClaw 可以为 Model Agent 的训练任务提供 Docker 化的执行环境，通过 MCP 桥接从 OpenClaw 调用容器内的训练脚本。

#### 启示 4：迭代实验设计 LLM 的模式

Agentomics 的 Experiment Design LLM 在每次新 Iteration 开始时，读取所有历史 Iteration 的摘要来设计下一次实验。这种"从历史中学习"的模式与 BioOpenClaw 的三层记忆系统天然契合：
- **MEMORY.md**（Layer 1）可存储跨会话的"Core Lessons"（如"ESM-2 在蛋白质稳定性任务上最佳 LoRA rank 为 8"）
- **experiments/ index**（Layer 3）可存储详细的实验摘要，供 Experiment Design 读取

#### 启示 5：验证集-测试集相关性确认泛化

Agentomics 发现优化验证集性能通常能泛化到测试集（中位相关性 0.964），但药物发现领域例外。这提示 BioOpenClaw 的 Watcher Agent 需要监控验证集-测试集的指标相关性——如果发现两者严重背离，应触发纠偏（如重新分割数据、更换数据表示策略）。

#### 启示 6：100% 的运行成功率是可达到的目标

Agentomics 在 60 次运行中实现了 100% 的成功率（每次都产出可用模型）。这归功于严格的步骤验证和重试机制。BioOpenClaw 的 Model Agent 也应设计类似的 checkpoint 验证链，确保每次训练运行都能产出有效的模型 artifact。

---

## 五、三项工作的横向对比

### 5.1 架构对比

| 维度 | AutoResearch | OpenClaw-RL | Agentomics |
|------|-------------|-------------|------------|
| **Agent 数量** | 单 Agent | 单 Agent（支持多流） | 单 Agent 多步骤 |
| **架构模式** | 循环修改代码 | 异步四组件 | 预定义步骤流水线 |
| **代码量** | 630 行 | 大型框架 | 中型框架 |
| **训练对象** | Agent 修改的外部模型 | Agent 自身的策略模型 | Agent 生成的外部 ML 模型 |
| **记忆系统** | Git log + results.tsv | Session-aware 日志 | Iteration Summary 累积 |
| **信任边界** | train.py vs prepare.py | Main-line vs Side turn | 步骤验证 + Docker 沙盒 |
| **安全隔离** | 文件权限 | API 加密 | Docker 容器化 |

### 5.2 训练范式对比

| 维度 | AutoResearch | OpenClaw-RL | Agentomics |
|------|-------------|-------------|------------|
| **训练什么** | 外部 GPT 模型 | OpenClaw Agent 策略 | 外部 ML 模型 |
| **如何训练** | 修改代码→训练→评估→保留/回滚 | 从对话信号中提取奖励→PPO | 生成完整代码→训练→验证→迭代 |
| **训练信号** | val_bpb 指标 | 用户反馈 + 工具输出 | 验证集指标 |
| **信号粒度** | 二元（改进/未改进） | 标量 + token 级别 | 多维指标 |
| **训练成本** | $50-200/晚 | 取决于模型规模 | ~$9.4/8小时 |

### 5.3 领域覆盖对比

| 维度 | AutoResearch | OpenClaw-RL | Agentomics |
|------|-------------|-------------|------------|
| **目标领域** | LLM 预训练 | 通用（对话/终端/GUI/SWE） | 生物医学 ML |
| **支持任务** | 语言模型训练 | 个性化 + 通用 Agent | 分类/回归 |
| **基础模型支持** | 内置 GPT 架构 | 任意 LLM（Qwen3 等） | ESM-2, HyenaDNA, RiNALMo, ChemBERTa 等 |
| **数据模态** | 文本 | 多模态 | DNA/RNA/蛋白质/小分子 |
| **与生信相关度** | 低（通用方法论可借鉴） | 中（框架可复用） | 高（直接领域重叠） |

---

## 六、对 BioOpenClaw 的综合启示

### 6.1 Model Agent 训练循环设计

综合三个项目的优势，BioOpenClaw Model Agent 的训练循环应采用以下设计：

```
┌─────────────────────────────────────────────────────────────────┐
│                BioOpenClaw Model Agent 训练循环                   │
│                                                                   │
│  Phase A（AutoResearch 模式）：                                    │
│    1. 读取 training_strategy.md（from SOUL.md + Research Agent）   │
│    2. 读取 MEMORY.md 中的 Core Lessons（历史最佳实践）              │
│    3. 读取 shared_memory/model_registry/ 中的基础模型信息           │
│    4. 生成/修改 lora_train.py                                     │
│    5. 在 Docker 容器中执行训练（固定时间窗口）                       │
│    6. eval_pipeline.py 计算验证指标（信任边界，不可修改）            │
│    7. 指标改进 → commit + 写入 experiments/ index                   │
│       指标未改进 → 回滚 + 写入 MEMORY.md 失败经验                   │
│    8. 重复                                                        │
│                                                                   │
│  Phase B（OpenClaw-RL 信号回收）：                                  │
│    9. Watcher 的纠偏指令 → OPD 指导性信号                           │
│    10. 历史实验的成功/失败 → Binary RL 评估性信号                    │
│    11. 异步更新 Model Agent 的策略                                  │
│                                                                   │
│  Phase C（Agentomics 式验证）：                                     │
│    12. 每步结果通过结构化验证                                       │
│    13. 验证失败则重试，超限则从头开始                                │
│    14. 最终产物：训练脚本 + 推理脚本 + 模型权重 + 报告               │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 多 Agent 协作优势

BioOpenClaw 相比三个参照项目的最大优势是**多 Agent 协作**。在单 Agent 系统中，一个 Agent 需要既懂数据、又懂模型、还懂文献。在 BioOpenClaw 中：

| 训练阶段 | 主导 Agent | 协作 Agent | 协作内容 |
|---------|-----------|-----------|---------|
| 数据准备 | Data Agent | Scout Agent | 推荐最适合的基础模型 |
| 训练策略 | Model Agent | Research Agent | 文献中的最佳超参和训练技巧 |
| 训练执行 | Model Agent | Watcher | 监控训练过程，检测异常 |
| 结果评估 | Model Agent | Research Agent | 将结果与文献 benchmark 对比 |
| 纠偏改进 | Watcher | Model Agent | 发送纠偏指令到 inbox |

### 6.3 记忆系统与实验管理的融合

三个项目分别使用了 Git（AutoResearch）、JSONL 日志（OpenClaw-RL）、Iteration Summary（Agentomics）来管理实验历史。BioOpenClaw 的三层记忆系统可以统一这些需求：

| 记忆层 | 存储内容 | 对应 |
|--------|---------|------|
| Layer 1: MEMORY.md | "ESM-2 最佳 LoRA rank: 8"等核心经验 | Agentomics 的跨 Iteration 学习 |
| Layer 2: active_context.md | 当前训练会话状态（正在运行的 Iteration、当前步骤） | AutoResearch 的 results.tsv |
| Layer 3: experiments/_index.md | 每次实验的完整摘要（超参、指标、模型路径） | Agentomics 的 Iteration Summary |
| Git history | 代码变更的完整追踪 | AutoResearch 的 git 记忆 |

### 6.4 建议新增的 shared_memory 资源

基于 Agentomics 的经验，建议在 `shared_memory/model_registry/` 中为每个基础模型增加：

```
shared_memory/model_registry/
├── _index.md                 ← 已有
├── ESM2.md                   ← 需增加：微调代码模板、已知最佳实践
├── scGPT.md                  ← 需增加：单细胞数据预处理规范
├── Geneformer.md             ← 需增加：cell embedding 提取方法
├── Evo2.md                   ← 需增加：长序列处理注意事项
├── HyenaDNA.md               ← 新增：DNA 序列基础模型
├── NucleotideTransformer.md  ← 新增：DNA 序列基础模型
└── templates/
    ├── lora_config_template.py    ← LoRA 配置模板
    ├── data_loader_template.py    ← 统一数据加载器
    └── eval_pipeline_template.py  ← 评估流水线模板
```

---

## 七、推荐的 Phase 2 行动项

基于上述分析，建议 BioOpenClaw Phase 2 的优先行动：

### P0（最高优先级）

1. **实现 Model Agent 训练循环原型**
   - 借鉴 AutoResearch 的三文件信任边界架构
   - 实现 `training_strategy.md` / `lora_train.py` / `eval_pipeline.py` 分离
   - 在 MCP Server 中添加 `run_lora_training` 和 `evaluate_model` 工具

2. **扩充 model_registry 基础模型信息**
   - 为 ESM2、scGPT、Geneformer、Evo2 添加微调代码模板
   - 添加 `foundation_models_info` 工具到 MCP Server

### P1（本阶段完成）

3. **实现实验记录管理**
   - 在 `shared_memory/experiments/_index.md` 中定义实验摘要格式
   - 实现 `log_experiment` 工具，自动记录每次训练的超参、指标、模型路径

4. **设计 Model Agent ↔ Data Agent ↔ Research Agent 的协作协议**
   - 定义 inbox 消息格式：训练请求、数据准备请求、文献查询请求
   - 实现多 Agent 流水线的步骤验证检查点

### P2（Phase 3 预备）

5. **评估 OpenClaw-RL 集成可行性**
   - 测试 OpenClaw-RL 在 BioOpenClaw 场景下的部署
   - 设计 Watcher 纠偏 → OPD 训练信号的转化管道

6. **Docker 化训练执行环境**
   - 为 Model Agent 的训练任务构建标准 Docker 镜像
   - 预装 PyTorch、PEFT、Scanpy 等依赖
   - 通过 MCP 桥接从 OpenClaw 调用容器内的训练脚本

---

## 参考文献

1. Karpathy, A. (2026). AutoResearch: AI agents running research on single-GPU nanochat training automatically. GitHub: https://github.com/karpathy/autoresearch

2. Wang, Y., Chen, X., Jin, X., Wang, M., & Yang, L. (2026). OpenClaw-RL: Train Any Agent Simply by Talking. arXiv:2603.10165.

3. Alexiou, P. et al. (2026). Agentomics: An Agentic System that Autonomously Develops Novel State-of-the-art Solutions for Biomedical Machine Learning Tasks. bioRxiv 2026.01.27.702049.

4. Jiang, Z. et al. (2025). AIDE: AI-Driven Exploration in the Space of Code. arXiv:2502.13138.

5. Jin, R. et al. (2025). STELLA: Self-Evolving LLM Agent for Biomedical Research. arXiv:2507.02004.

6. Wang, Y. et al. (2026). RLAnything: Integrating Step-wise Rewards for Agentic RL. (referenced in OpenClaw-RL).

---

> **文档维护者**: BioOpenClaw Research Agent
> **最后更新**: 2026-03-15
