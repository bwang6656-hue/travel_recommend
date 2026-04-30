# 基于scenic_spots_30000_llm.csv构建RAG系统升级AI行程规划接口

## 一、现状分析

### 当前问题
1. **AI行程接口需要结构化输入**：`/recommend/ai` 端点要求用户传入 `spots` 列表（含 name/city/type），无法理解自然语言
2. **LLM调用过于简单**：仅将景点名称拼接成 prompt，未利用 CSV 中丰富的9个字段（price, open_time, best_season, tags 等）
3. **无知识库支撑**：LLM完全依赖自身知识，对景点详情（开放时间、门票、拥挤度等）一无所知，容易产生幻觉
4. **无RAG架构**：项目没有任何向量检索、知识库注入机制

### 数据资源
- `scenic_spots_30000_llm.csv`：15列丰富数据（id, name_zh, city, rating, address, type, price, open_time, best_season, crowd_level, recommended_duration, tags, latitude, longitude, popularity）
- 通义千问 API（dashscope SDK）已集成
- Neo4j 知识图谱已有景点数据

---

## 二、技术方案

### 架构设计
```
用户自然语言查询
    ↓
[意图理解] → 提取城市/偏好/天数/季节等关键信息
    ↓
[向量检索] → 从FAISS知识库中检索相关景点文档
    ↓
[知识图谱增强] → 从Neo4j获取景点间关系（同城/同类）
    ↓
[上下文组装] → 将检索结果+图谱关系组装为结构化Prompt
    ↓
[LLM生成] → 调用通义千问生成行程方案
    ↓
结构化行程响应
```

### 核心组件
1. **知识库构建**：将CSV数据转为文本文档 → 向量化 → 存入FAISS
2. **Embedding模型**：使用 dashscope 的 `text-embedding-v2` 模型（与通义千问同一生态）
3. **向量存储**：FAISS（轻量、无需额外服务、适合本地部署）
4. **检索策略**：混合检索（向量相似度 + 元数据过滤）
5. **LLM生成**：通义千问 qwen-turbo，升级为对话式 messages API

---

## 三、实施步骤

### 步骤1：安装依赖并更新requirements.txt
- 新增：`faiss-cpu`（向量检索）、`langchain`（RAG框架）、`langchain-community`（FAISS集成）
- 保留现有依赖不变

### 步骤2：构建知识库文档构建器 `app/services/knowledge_base_builder.py`
- 读取 `scenic_spots_30000_llm.csv`
- 为每个景点生成结构化文本文档，格式如：
  ```
  景点名称：故宫博物院
  所在城市：北京
  评分：4.7
  地址：景山前街4号
  类型：世界遗产|博物馆
  门票价格：30元
  开放时间：09:00-18:00
  最佳季节：秋季
  拥挤程度：高
  建议游玩时长：1-2小时
  标签：网红打卡,休闲度假,自然风光
  人气值：100
  ```
- 生成元数据字典（city, type, price_range, season 等）用于过滤
- 将构建结果持久化到本地文件（避免每次启动重新构建）

### 步骤3：构建向量存储服务 `app/services/vector_store_service.py`
- 使用 dashscope 的 `text-embedding-v2` 模型生成文档向量
- 构建 FAISS 索引并保存到 `saved_models/faiss_index/`
- 提供检索接口：`search(query_text, top_k=20, filters={})` 
- 支持元数据过滤（按城市、季节、价格区间等）
- 启动时自动加载已有索引，无索引时自动构建

### 步骤4：构建RAG服务 `app/services/rag_service.py`
- **意图理解**：用LLM从自然语言中提取结构化信息（城市、天数、偏好、季节、预算等）
- **混合检索**：向量检索 + Neo4j图谱关系查询
- **上下文组装**：将检索到的景点信息格式化为结构化Prompt
- **行程生成**：调用通义千问生成行程，使用对话式 messages API
- 核心方法：`plan_itinerary(query: str) -> dict`

### 步骤5：升级AI服务 `app/services/ai_service.py`
- 保留原有 `generate_itinerary` 方法（向后兼容）
- 新增 `generate_itinerary_from_query(query: str)` 方法
- 升级LLM调用方式：从 `prompt` 参数改为 `messages` 对话格式
- 增大 `max_tokens` 到 2000（多天行程需要更多输出）
- 添加系统提示词（System Prompt）定义AI角色和行为规范

### 步骤6：更新API Schema `app/schemas/schemas.py`
- 新增 `NaturalLanguageTripRequest`：
  ```python
  class NaturalLanguageTripRequest(BaseModel):
      query: str = Field(..., description="自然语言行程需求，如'我想去北京玩3天，喜欢历史文化'")
  ```
- 新增 `NaturalLanguageTripResponse`：
  ```python
  class NaturalLanguageTripResponse(BaseModel):
      query: str
      itinerary: str
      related_spots: List[Dict]  # 检索到的相关景点
      days: int
      city: Optional[str]
  ```

### 步骤7：新增API端点 `app/api/recommend.py`
- 新增 `POST /recommend/ai/chat` 端点，接收自然语言查询
- 保留原 `POST /recommend/ai` 端点不变（向后兼容）
- 新端点调用 RAG 服务的完整流程

### 步骤8：应用启动时初始化RAG组件 `main.py`
- 在 lifespan 中初始化向量存储服务（加载/构建FAISS索引）
- 预热embedding模型

---

## 四、文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `requirements.txt` | 修改 | 新增 faiss-cpu, langchain, langchain-community |
| `app/services/knowledge_base_builder.py` | 新建 | 知识库文档构建器 |
| `app/services/vector_store_service.py` | 新建 | 向量存储与检索服务 |
| `app/services/rag_service.py` | 新建 | RAG核心服务（意图理解+检索+生成） |
| `app/services/ai_service.py` | 修改 | 升级LLM调用方式，新增自然语言接口 |
| `app/schemas/schemas.py` | 修改 | 新增自然语言请求/响应Schema |
| `app/api/recommend.py` | 修改 | 新增 `/recommend/ai/chat` 端点 |
| `app/config/config.py` | 修改 | 新增RAG相关配置项 |
| `main.py` | 修改 | lifespan中初始化RAG组件 |

---

## 五、关键设计决策

1. **使用FAISS而非ChromaDB**：FAISS轻量、无需额外服务进程、适合毕设场景
2. **使用dashscope embedding而非sentence-transformers**：与通义千问同一生态，中文效果更好，无需下载本地模型
3. **保留原接口**：`/recommend/ai` 保持不变，新增 `/recommend/ai/chat` 支持自然语言
4. **混合检索策略**：向量检索 + Neo4j图谱关系，兼顾语义相似性和结构化关系
5. **知识库持久化**：FAISS索引和文档数据保存到磁盘，避免每次启动重建
