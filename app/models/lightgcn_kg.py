import torch
import torch.nn as nn
from torch_geometric.nn import GCNConv
from app.services.knowledge_graph_service import feature_extractor

class LightGCNWithKG(nn.Module):
    def __init__(self, num_users, num_items, embedding_dim=64, num_layers=3):
        super(LightGCNWithKG, self).__init__()
        self.num_users = num_users
        self.num_items = num_items
        self.embedding_dim = embedding_dim
        self.num_layers = num_layers
        
        # 初始化用户和物品嵌入
        self.user_embedding = nn.Embedding(num_users, embedding_dim)
        self.item_embedding = nn.Embedding(num_items, embedding_dim)
        nn.init.normal_(self.user_embedding.weight, std=0.1)
        nn.init.normal_(self.item_embedding.weight, std=0.1)
        
        # 知识图谱特征维度
        self.kg_feature_dim = feature_extractor.get_feature_dim()
        
        # 特征融合层
        self.feature_fusion = nn.Linear(self.kg_feature_dim, embedding_dim)
        nn.init.normal_(self.feature_fusion.weight, std=0.1)
        
        # 定义图卷积层
        self.convs = nn.ModuleList()
        for _ in range(num_layers):
            self.convs.append(GCNConv(embedding_dim, embedding_dim, add_self_loops=False))
    
    def forward(self, edge_index, item_features=None):
        # 获取初始嵌入
        user_emb = self.user_embedding.weight
        item_emb = self.item_embedding.weight
        
        # 融合知识图谱特征
        if item_features is not None:
            kg_emb = self.feature_fusion(item_features)
            item_emb = item_emb + kg_emb
        
        # 合并用户和物品嵌入
        x = torch.cat([user_emb, item_emb], dim=0)
        
        # 保存每一层的嵌入
        emb_list = [x]
        
        # 多层图卷积
        for conv in self.convs:
            x = conv(x, edge_index)
            emb_list.append(x)
        
        # 取所有层嵌入的平均值
        output = torch.stack(emb_list, dim=0).mean(dim=0)
        
        # 分离用户和物品嵌入
        user_emb = output[:self.num_users]
        item_emb = output[self.num_users:]
        
        return user_emb, item_emb
    
    def predict(self, user_ids, item_ids, item_features=None):
        # 获取用户和物品嵌入
        user_emb, item_emb = self.forward(self.edge_index, item_features)
        
        # 计算用户和物品的内积作为预测分数
        user_emb = user_emb[user_ids]
        item_emb = item_emb[item_ids]
        scores = (user_emb * item_emb).sum(dim=1)
        
        return scores
    
    def recommend(self, user_id, top_k=10, exclude_items=None, item_features=None):
        # 获取用户和物品嵌入
        user_emb, item_emb = self.forward(self.edge_index, item_features)
        
        # 获取目标用户的嵌入
        user_emb = user_emb[user_id].unsqueeze(0)
        
        # 计算用户与所有物品的相似度
        scores = torch.matmul(user_emb, item_emb.t()).squeeze()
        
        # 排除已交互的物品
        if exclude_items is not None:
            scores[exclude_items] = -float('inf')
        
        # 获取Top-K推荐
        _, top_indices = torch.topk(scores, top_k)
        
        return top_indices.cpu().numpy().tolist()
    
    def set_edge_index(self, edge_index):
        # 设置图的边索引
        self.edge_index = edge_index
