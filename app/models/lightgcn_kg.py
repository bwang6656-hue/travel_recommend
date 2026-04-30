import torch
import torch.nn as nn
from app.services.knowledge_graph_service import feature_extractor

class LightGCNWithKG(nn.Module):
    def __init__(self, num_users, num_items, embedding_dim=64, num_layers=3):
        super(LightGCNWithKG, self).__init__()
        self.num_users = num_users
        self.num_items = num_items
        self.embedding_dim = embedding_dim
        self.num_layers = num_layers
        
        self.user_embedding = nn.Embedding(num_users, embedding_dim)
        self.item_embedding = nn.Embedding(num_items, embedding_dim)
        nn.init.normal_(self.user_embedding.weight, std=0.1)
        nn.init.normal_(self.item_embedding.weight, std=0.1)
        
        self.kg_feature_dim = feature_extractor.get_feature_dim()
        
        self.feature_fusion = nn.Sequential(
            nn.Linear(self.kg_feature_dim, embedding_dim),
            nn.LayerNorm(embedding_dim),
            nn.Dropout(0.1)
        )
        
        self.gate_linear = nn.Linear(embedding_dim, embedding_dim)
        
        self.alpha = nn.Parameter(torch.tensor(0.5))
    
    def forward(self, edge_index, item_features=None):
        user_emb = self.user_embedding.weight
        item_emb = self.item_embedding.weight
        
        if item_features is not None:
            kg_emb = self.feature_fusion(item_features)
            gate = torch.sigmoid(self.gate_linear(kg_emb))
            item_emb = item_emb + gate * kg_emb
        
        x = torch.cat([user_emb, item_emb], dim=0)
        
        num_nodes = self.num_users + self.num_items
        
        row = edge_index[0]
        col = edge_index[1]
        
        deg = torch.zeros(num_nodes, dtype=torch.float32, device=edge_index.device)
        deg.scatter_add_(0, row, torch.ones(row.shape[0], dtype=torch.float32, device=edge_index.device))
        deg_inv_sqrt = torch.pow(deg, -0.5)
        deg_inv_sqrt[deg_inv_sqrt == float('inf')] = 0
        
        norm = deg_inv_sqrt[row] * deg_inv_sqrt[col]
        
        emb_list = [x]
        
        for _ in range(self.num_layers):
            norm_msg = norm.unsqueeze(1) * x[row]
            x_new = torch.zeros_like(x)
            x_new.index_add_(0, col, norm_msg)
            x = x_new
            emb_list.append(x)
        
        alpha = torch.sigmoid(self.alpha)
        output = (1 - alpha) * emb_list[0] + alpha * torch.stack(emb_list[1:], dim=0).mean(dim=0)
        
        user_emb = output[:self.num_users]
        item_emb = output[self.num_users:]
        
        return user_emb, item_emb
    
    def predict(self, user_ids, item_ids, item_features=None):
        user_emb, item_emb = self.forward(self.edge_index, item_features)
        
        user_emb = user_emb[user_ids]
        item_emb = item_emb[item_ids]
        scores = (user_emb * item_emb).sum(dim=1)
        
        return scores
    
    def recommend(self, user_id, top_k=10, exclude_items=None, item_features=None):
        user_emb, item_emb = self.forward(self.edge_index, item_features)
        
        user_emb = user_emb[user_id].unsqueeze(0)
        
        scores = torch.matmul(user_emb, item_emb.t()).squeeze()
        
        if exclude_items is not None:
            scores[exclude_items] = -float('inf')
        
        _, top_indices = torch.topk(scores, top_k)
        
        return top_indices.cpu().numpy().tolist()
    
    def set_edge_index(self, edge_index):
        self.edge_index = edge_index
