import torch
import torch.nn as nn
import torch.optim as optim
from app.models.lightgcn_kg import LightGCNWithKG
from app.services.data_service import data_processor
import os

class ModelTrainer:
    def __init__(self, embedding_dim=64, num_layers=3, learning_rate=0.001, weight_decay=1e-4):
        self.embedding_dim = embedding_dim
        self.num_layers = num_layers
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.model = None
        self.optimizer = None
    
    def init_model(self, num_users, num_items):
        """初始化模型"""
        self.model = LightGCNWithKG(
            num_users=num_users,
            num_items=num_items,
            embedding_dim=self.embedding_dim,
            num_layers=self.num_layers
        )
        self.optimizer = optim.Adam(
            self.model.parameters(),
            lr=self.learning_rate,
            weight_decay=self.weight_decay
        )
    
    def train(self, edge_index, item_features, epochs=100, batch_size=2048):
        """训练模型"""
        self.model.train()
        
        for epoch in range(epochs):
            self.optimizer.zero_grad()
            
            # 前向传播
            user_emb, item_emb = self.model(edge_index, item_features)
            
            # 计算损失（使用BPR损失）
            loss = self.bpr_loss(user_emb, item_emb, edge_index)
            
            # 反向传播
            loss.backward()
            self.optimizer.step()
            
            if (epoch + 1) % 10 == 0:
                print(f"Epoch {epoch+1}/{epochs}, Loss: {loss.item():.4f}")
    
    def bpr_loss(self, user_emb, item_emb, edge_index):
        """计算BPR损失"""
        # 获取用户和正样本的边
        user_indices = edge_index[0][::2]  # 只取用户到物品的边
        pos_item_indices = edge_index[1][::2] - user_emb.shape[0]  # 转换为物品索引
        
        # 生成负样本
        neg_item_indices = torch.randint(0, item_emb.shape[0], (pos_item_indices.shape[0],), device=user_emb.device)
        
        # 计算正样本和负样本的分数
        pos_scores = (user_emb[user_indices] * item_emb[pos_item_indices]).sum(dim=1)
        neg_scores = (user_emb[user_indices] * item_emb[neg_item_indices]).sum(dim=1)
        
        # 计算BPR损失
        loss = -torch.log(torch.sigmoid(pos_scores - neg_scores)).mean()
        
        return loss
    
    def evaluate(self, test_data, top_k=10):
        """评估模型"""
        self.model.eval()
        
        with torch.no_grad():
            # 计算评估指标
            precision, recall, ndcg = self.calculate_metrics(test_data, top_k)
            
            print(f"Precision@{top_k}: {precision:.4f}")
            print(f"Recall@{top_k}: {recall:.4f}")
            print(f"NDCG@{top_k}: {ndcg:.4f}")
            
            return precision, recall, ndcg
    
    def calculate_metrics(self, test_data, top_k):
        """计算评估指标"""
        precision_list = []
        recall_list = []
        ndcg_list = []
        
        for user_id, test_items in test_data.items():
            # 获取用户索引
            user_idx = data_processor.user_id_to_idx(user_id)
            if user_idx == -1:
                continue
            
            # 获取用户已交互的物品
            exclude_items = [data_processor.spot_id_to_idx(spot_id) for spot_id in test_items]
            exclude_items = [idx for idx in exclude_items if idx != -1]
            
            # 获取推荐列表
            item_features = data_processor.get_item_features()
            recommendations = self.model.recommend(user_idx, top_k, exclude_items, item_features)
            
            # 转换为景点ID
            recommended_spot_ids = [data_processor.idx_to_spot_id(idx) for idx in recommendations]
            
            # 计算指标
            intersection = set(recommended_spot_ids) & set(test_items)
            precision = len(intersection) / top_k
            recall = len(intersection) / len(test_items) if len(test_items) > 0 else 0
            ndcg = self.calculate_ndcg(recommended_spot_ids, test_items, top_k)
            
            precision_list.append(precision)
            recall_list.append(recall)
            ndcg_list.append(ndcg)
        
        return sum(precision_list) / len(precision_list), sum(recall_list) / len(recall_list), sum(ndcg_list) / len(ndcg_list)
    
    def calculate_ndcg(self, recommendations, ground_truth, top_k):
        """计算NDCG"""
        dcg = 0.0
        idcg = 0.0
        
        # 计算DCG
        for i, item in enumerate(recommendations[:top_k]):
            if item in ground_truth:
                dcg += 1.0 / (i + 1)
        
        # 计算IDCG
        for i in range(min(len(ground_truth), top_k)):
            idcg += 1.0 / (i + 1)
        
        return dcg / idcg if idcg > 0 else 0.0
    
    def save_model(self, path):
        """保存模型"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict()
        }, path)
    
    def load_model(self, path):
        """加载模型"""
        checkpoint = torch.load(path)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
    
    def get_model(self):
        """获取模型"""
        return self.model

# 全局模型训练器实例
model_trainer = ModelTrainer()
