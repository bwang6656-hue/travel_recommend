# Neo4j知识图谱导入计划

## 1. 项目背景

用户需要将新数据 `E:\travel_recommend\data\scenic_spots_30000.csv` 导入到Neo4j知识图谱中，用于训练GCN模型和协同过滤算法。同时保留原有关系结构，并保证关系名称不变。另一部分数据 `E:\travel_recommend\data\scenic_spots_30000_llm.csv` 无需导入Neo4j，将用于训练LLM问答模型。

## 2. 现有知识图谱结构

从Neo4j数据库信息中，我们可以看到：

### 现有节点类型：
- Category
- City
- ScenicSpot
- travel

### 现有关系类型：
- IN_SAME_CITY_AS
- SAME_CATEGORY_AS

### 现有属性键：
- address, city, data, id, name, nodes, Property1, rating, relationships, spot_id, style, type, visualisation

## 3. 新数据结构分析

### 数据文件：`scenic_spots_30000.csv`

**字段结构：**
- id: 景点ID
- name_zh: 景点名称（中文）
- city: 城市
- rating: 评分
- address: 地址
- type: 类型（可能包含多个类型，用分号或竖线分隔）

**数据示例：**
```
id,name_zh,city,rating,address,type
1,天安门广场,北京,4.8,东长安街,风景名胜;风景名胜;红色景区|风景名胜;公园广场;城市广场
2,天安门,北京,4.8,长安街北侧,风景名胜;风景名胜;国家级景点
```

## 4. 导入计划

### 4.1 旧数据处理

**重要决策：** 由于新数据包含30000条记录，远大于现有137个节点，建议先删除旧数据，以避免数据冗余和冲突。

**删除步骤：**
1. 删除所有关系
2. 删除所有节点
3. 保留约束和索引结构

### 4.2 数据处理步骤

1. **数据读取与清洗**
   - 读取CSV文件
   - 处理类型字段（拆分多个类型）
   - 去除重复数据
   - 处理空值

2. **节点数据准备**
   - ScenicSpot节点：id, name, city, rating, address
   - City节点：name
   - Category节点：从type字段中提取

3. **关系数据准备**
   - ScenicSpot -[:LOCATED_IN]-> City
   - ScenicSpot -[:HAS_CATEGORY]-> Category
   - 重建原有关系：IN_SAME_CITY_AS, SAME_CATEGORY_AS

### 4.3 Neo4j导入策略

**选择策略：** 使用Python Neo4j Driver结合批量操作，实现高效导入。

**优化措施：**
- 使用事务批量处理
- 批量创建节点和关系
- 利用参数化查询提高性能

### 4.4 关系建立方案

1. **重建原有关系**
   - IN_SAME_CITY_AS：景点之间的同城市关系
   - SAME_CATEGORY_AS：景点之间的同类别关系

2. **新增关系**
   - LOCATED_IN：景点与城市的所属关系
   - HAS_CATEGORY：景点与类别的从属关系

### 4.5 导入流程

1. **连接Neo4j数据库**
2. **删除旧数据**
   - 删除所有关系
   - 删除所有节点

3. **创建约束**
   - 为ScenicSpot节点的id属性创建唯一约束
   - 为City节点的name属性创建唯一约束
   - 为Category节点的name属性创建唯一约束

4. **导入City节点**
   - 提取所有城市名称
   - 去重后批量导入

5. **导入Category节点**
   - 从type字段中提取所有类别
   - 去重后批量导入

6. **导入ScenicSpot节点**
   - 批量导入景点基本信息

7. **建立关系**
   - 批量建立LOCATED_IN关系
   - 批量建立HAS_CATEGORY关系
   - 批量重建IN_SAME_CITY_AS关系
   - 批量重建SAME_CATEGORY_AS关系

8. **验证导入结果**
   - 检查节点数量
   - 检查关系数量
   - 抽样验证数据准确性

## 5. 技术实现

### 5.1 所需依赖

- Python 3.7+
- neo4j-driver
- pandas
- numpy

### 5.2 代码结构

```
app/
├── scripts/
│   └── neo4j_import.py  # 导入脚本
└── services/
    └── neo4j_service.py  # Neo4j服务
```

### 5.3 关键函数

1. **数据读取与处理**
   - `read_csv_data()`: 读取CSV文件
   - `process_category_data()`: 处理类型数据

2. **Neo4j操作**
   - `connect_neo4j()`: 连接Neo4j数据库
   - `clear_old_data()`: 清除旧数据
   - `create_constraints()`: 创建约束
   - `import_cities()`: 批量导入城市节点
   - `import_categories()`: 批量导入类别节点
   - `import_scenic_spots()`: 批量导入景点节点
   - `create_relationships()`: 批量创建关系

3. **验证函数**
   - `validate_import()`: 验证导入结果

## 6. 时间估计

- 数据处理：10分钟
- 旧数据清理：5分钟
- 节点导入：15分钟
- 关系建立：20分钟
- 验证：5分钟

**总时间：约55分钟**

## 7. 风险评估

### 7.1 潜在风险

1. **数据质量问题**
   - 重复数据
   - 空值
   - 格式不一致

2. **Neo4j性能问题**
   - 导入速度慢
   - 内存不足

3. **关系建立复杂度**
   - 类别拆分复杂度
   - 关系数量大

### 7.2 风险缓解措施

1. **数据质量控制**
   - 数据清洗步骤
   - 异常处理

2. **性能优化**
   - 批量导入（每批次1000条）
   - 事务管理
   - 索引优化

3. **关系建立优化**
   - 批量处理
   - 并行处理（可选）

## 8. 后续工作

1. **数据验证**
   - 确认所有数据已正确导入
   - 验证关系完整性

2. **模型训练准备**
   - 提取训练数据
   - 准备GCN模型输入

3. **性能评估**
   - 评估知识图谱查询性能
   - 优化查询语句

## 9. 结论

本计划提供了一个高效的Neo4j知识图谱导入方案，包括旧数据清理、数据处理、关系建立和验证步骤。通过批量操作和优化策略，可以在约1小时内完成30000条数据的导入，为后续的GCN模型训练和协同过滤算法提供基础。

同时，另一部分数据 `scenic_spots_30000_llm.csv` 将保留在本地，用于训练LLM问答模型，实现智能客服功能。