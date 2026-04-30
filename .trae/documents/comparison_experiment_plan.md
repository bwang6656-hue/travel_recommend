# 四模型对比实验计划

## 1. 目标

基于已有的 LightGCN 和 LightGCN+KG 模型，新增 GCN Baseline 和 UserCF 模型，对四个模型进行统一对比实验，通过 Precision@K、Recall@K、Hit Ratio@K、NDCG@K 四个指标证明哪个效果最好。

## 2. 现有代码分析

### 已有模型
| 模型 | 文件 | 状态 |
|------|------|------|
| LightGCN | `app/models/lightgcn.py` | ✅ 已有，使用 GCNConv 但无特征变换和非线性激活 |
| LightGCN+KG | `app/models/lightgcn_kg.py` | ✅ 已有，在 LightGCN 基础上融合知识图谱特征 |
| GCN Baseline | `app/models/gcn.py` | ❌ 不存在，需新建 |
| UserCF | `app/models/usercf.py` | ❌ 不存在，需新建 |

### 已有服务
| 服务 | 文件 | 说明 |
|------|------|------|
| DataProcessor | `app/services/data_service.py` | 从Neo4j加载景点，构建用户-物品交互图 |
| ModelTrainer | `app/services/model_service.py` | 仅训练 LightGCNWithKG，评估缺 Hit Ratio |
| KnowledgeGraphFeatureExtractor | `app/services/knowledge_graph_service.py` | 从Neo4j提取城市/类型/评分特征 |
| Neo4j Service | `app/services/neo4j_service.py` | Neo4j数据访问、协同过滤推荐 |

### 关键问题
1. **缺少 GCN Baseline 模型**：需要标准 GCN（含特征变换 + 非线性激活），与 LightGCN（去除这两项）形成对比
2. **缺少 UserCF 模型**：需要传统基于用户的协同过滤，基于余弦相似度
3. **ModelTrainer 仅支持 LightGCNWithKG**：需要重构为通用训练器，支持四种模型
4. **评估指标缺少 Hit Ratio**：当前只有 Precision/Recall/NDCG，需增加 Hit Ratio
5. **缺少统一实验脚本**：需要 `train.py` 和 `evaluate.py` 统一训练和评估四个模型

## 3. 实现方案

### 3.1 新建 GCN Baseline 模型 (`app/models/gcn.py`)

**与 LightGCN 的核心区别**：GCN 保留特征变换（Linear）和非线性激活（ReLU），LightGCN 去除了这两项。

```python
class GCN(nn.Module):
    def __init__(self, num_users, num_items, embedding_dim=64, num_layers=3):
        # 用户/物品嵌入
        self.embedding = nn.Embedding(num_users + num_items, embedding_dim)
        # GCN层：包含特征变换 + 非线性激活（与LightGCN的区别）
        self.convs = nn.ModuleList([
            GCNConv(embedding_dim, embedding_dim, add_self_loops=False)
            for _ in range(num_layers)
        ])
        self.leaky_relu = nn.LeakyReLU(0.2)  # 非线性激活
    
    def forward(self, edge_index):
        # 多层图卷积 + 非线性激活
        for conv in self.convs:
            x = conv(x, edge_index)
            x = self.leaky_relu(x)  # LightGCN没有这步
        # 分离用户/物品嵌入
        return user_emb, item_emb
```

### 3.2 新建 UserCF 模型 (`app/models/usercf.py`)

**核心思路**：基于用户-物品交互矩阵计算用户间余弦相似度，推荐相似用户喜欢的物品。

```python
class UserCF:
    def __init__(self, k_neighbors=20):
        self.k_neighbors = k_neighbors
        self.user_similarity = None  # 用户相似度矩阵
        self.interaction_matrix = None  # 用户-物品交互矩阵
    
    def fit(self, edge_index, num_users, num_items):
        # 构建交互矩阵
        # 计算用户间余弦相似度
        # 选取Top-K相似用户
    
    def predict(self, user_id, item_ids):
        # 基于相似用户的加权评分预测
    
    def recommend(self, user_id, top_k=10, exclude_items=None):
        # 生成Top-K推荐列表
```

### 3.3 数据加载策略

**优先使用 Neo4j 图数据库**，数据来源：
- 景点数据：从 Neo4j 的 `ScenicSpot` 节点加载（已导入 `E:\travel_data\scenic_spots_30000.csv`）
- 用户交互数据：从 MySQL `user_footprint` 表加载
- 知识图谱特征：从 Neo4j 提取城市/类型/评分特征

**数据流**：
```
Neo4j ScenicSpot → DataProcessor._init_mappings() → spot_id↔index 映射
MySQL user_footprint → DataProcessor.process_user_footprints() → edge_index
Neo4j ScenicSpot → KnowledgeGraphFeatureExtractor → item_features
```

### 3.4 重构统一训练脚本 (`train.py`)

**功能**：统一训练四个模型，保存模型权重。

```python
# 训练流程
1. 从Neo4j加载景点数据
2. 从MySQL加载用户足迹数据
3. 划分训练/测试集（80%/20%）
4. 训练四个模型：
   - UserCF：无需梯度训练，直接计算相似度矩阵
   - GCN：BPR损失训练
   - LightGCN：BPR损失训练
   - LightGCN+KG：BPR损失训练 + 知识图谱特征
5. 保存模型到 saved_models/ 目录
```

### 3.5 新建统一评估脚本 (`evaluate.py`)

**功能**：加载四个训练好的模型，统一评估并生成对比报告。

```python
# 评估指标
- Precision@K: 推荐列表中正确项的比例
- Recall@K: 测试集中正确项被推荐出的比例
- Hit Ratio@K: 至少有一个正确项被推荐的用户比例
- NDCG@K: 归一化折损累积增益

# K值设置
K = [5, 10, 20]

# 输出格式
| 模型 | Precision@5 | Recall@5 | HR@5 | NDCG@5 | Precision@10 | ... |
```

### 3.6 修改 `model_service.py`

**改动**：
1. 增加通用模型初始化方法，支持四种模型（通过 model_type 参数选择）
2. 评估方法增加 Hit Ratio 指标
3. BPR 损失计算兼容无 item_features 的情况（GCN 和 LightGCN 不需要 KG 特征）
4. 训练方法兼容不同模型的 forward 签名

## 4. 文件修改清单

| 操作 | 文件路径 | 说明 |
|------|----------|------|
| **新建** | `app/models/gcn.py` | GCN Baseline 模型 |
| **新建** | `app/models/usercf.py` | UserCF 协同过滤模型 |
| **新建** | `train.py` | 统一训练脚本 |
| **新建** | `evaluate.py` | 统一评估脚本 |
| **修改** | `app/services/model_service.py` | 增加通用训练/评估支持，增加 Hit Ratio |

## 5. 实验设计

### 5.1 数据准备
- 景点数据：从 Neo4j 图数据库加载（`ScenicSpot` 节点）
- 用户交互数据：从 MySQL `user_footprint` 表加载
- 知识图谱特征：从 Neo4j 提取城市/类型/评分
- 训练/测试划分：80% 训练，20% 测试（按用户交互随机划分）

### 5.2 超参数设置（统一控制变量）
| 参数 | 值 |
|------|-----|
| embedding_dim | 64 |
| num_layers | 3 |
| learning_rate | 0.001 |
| weight_decay | 1e-4 |
| epochs | 100 |
| batch_size | 2048 |
| K_neighbors (UserCF) | 20 |
| K (评估) | 5, 10, 20 |

### 5.3 评估指标
| 指标 | 公式 | 含义 |
|------|------|------|
| Precision@K | \|推荐∩真实\| / K | 推荐准确率 |
| Recall@K | \|推荐∩真实\| / \|真实\| | 召回率 |
| Hit Ratio@K | 有命中用户数 / 总用户数 | 覆盖率 |
| NDCG@K | DCG@K / IDCG@K | 排序质量 |

### 5.4 预期结果排序
LightGCN+KG > LightGCN > GCN > UserCF

## 6. 执行步骤

1. 新建 `app/models/gcn.py`（GCN Baseline 模型）
2. 新建 `app/models/usercf.py`（UserCF 协同过滤模型）
3. 修改 `app/services/model_service.py`（增加通用训练/评估支持，增加 Hit Ratio）
4. 新建 `train.py`（统一训练脚本）
5. 新建 `evaluate.py`（统一评估脚本）
6. 运行训练和评估，生成对比结果
