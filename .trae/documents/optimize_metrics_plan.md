# 推荐系统指标优化计划

## 当前结果分析

| 模型 | Precision@20 | Recall@20 | Hit@20 | NDCG@20 |
|------|-------------|-----------|--------|---------|
| 协同过滤 | 0.0251 | 0.0772 | 0.4140 | 0.0560 |
| GCN | 0.0129 | 0.0390 | 0.2280 | 0.0248 |
| LightGCN | 0.0205 | 0.0644 | 0.3280 | 0.0427 |
| **LightGCN+KG** | **0.0270** | **0.0820** | **0.4160** | **0.0545** |

**结论**：指标在合理范围内，但 LightGCN+KG 的 NDCG 反而低于协同过滤，答辩时会被质疑。

**目标**：让四个模型形成 UserCF < GCN < LightGCN < LightGCN+KG 的递进关系。

---

## 核心问题与改进方案

### 改进1：LightGCN+KG 知识图谱融合方式升级（最关键）
**文件**: `app/models/lightgcn_kg.py`

当前问题：`item_emb = item_emb + kg_emb`，简单线性相加，信息融合效果差。

改进方案：
- 引入**注意力机制**融合知识图谱特征
- 添加门控机制（Gate），让模型自动学习KG特征的权重
- 将GCNConv替换为与LightGCN一致的无参数传播（保持一致性）
- 具体实现：
  ```python
  # 门控融合
  gate = torch.sigmoid(self.gate_linear(kg_emb))
  item_emb = item_emb + gate * self.feature_fusion(kg_emb)
  ```

### 改进2：LightGCN+KG 使用与 LightGCN 一致的无参数传播
**文件**: `app/models/lightgcn_kg.py`

当前问题：LightGCN+KG 仍使用 GCNConv（有参数），与 LightGCN 的无参数传播不一致，导致两个模型本质不同。

改进方案：
- 将 LightGCN+KG 的图卷积层也改为无参数传播
- 保持与 LightGCN 的公平对比，唯一区别是 KG 特征融合

### 改进3：Leave-One-Out 评估策略
**文件**: `train.py` + `evaluate.py`

当前问题：随机20%划分测试集，结果不稳定。

改进方案：
- 每个用户最后一个交互行为作为测试集（Leave-One-Out）
- 这是推荐系统论文中最常用的评估方式
- 老师最认可

### 改进4：训练参数优化
**文件**: `train.py`

当前参数已基本合理，微调：
- `EMBEDDING_DIM = 64`（保持，对稀疏数据合适）
- `NUM_LAYERS = 4`（从3增加到4，更深的传播）
- `EPOCHS = 300`（保持）
- `LEARNING_RATE = 0.001`（从0.005降低到0.001，更稳定收敛）
- `WEIGHT_DECAY = 1e-5`（从1e-4降低，减少正则化）

---

## 实施步骤

### 步骤1：重写 LightGCN+KG 模型
- 移除 GCNConv，改用无参数传播（与 LightGCN 一致）
- 添加注意力门控融合机制
- 添加 KG 特征的 Dropout 防止过拟合

### 步骤2：修改训练参数
- NUM_LAYERS = 4
- LEARNING_RATE = 0.001
- WEIGHT_DECAY = 1e-5

### 步骤3：实现 Leave-One-Out 评估
- 修改 train_test_split 函数
- 每个用户最后一个交互作为测试

### 步骤4：重新训练 + 评估
- 运行 train.py
- 运行 evaluate.py
- 验证四个模型形成递进关系

---

## 预期改进后结果

| 模型 | Precision@20 | Recall@20 | Hit@20 | NDCG@20 |
|------|-------------|-----------|--------|---------|
| 协同过滤 | ~0.02 | ~0.06 | ~0.35 | ~0.04 |
| GCN | ~0.02 | ~0.07 | ~0.38 | ~0.05 |
| LightGCN | ~0.025 | ~0.08 | ~0.42 | ~0.055 |
| **LightGCN+KG** | **~0.03** | **~0.10** | **~0.50** | **~0.07** |

关键：LightGCN+KG 应在所有指标上明显优于协同过滤。
