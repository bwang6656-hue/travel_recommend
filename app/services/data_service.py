import torch
from torch_geometric.data import Data
from app.services.neo4j_service import get_all_spots_from_db
from app.services.knowledge_graph_service import feature_extractor
from collections import defaultdict
import numpy as np

class DataProcessor:
    def __init__(self):
        self.spot_id_to_index = {}
        self.user_id_to_index = {}
        self.index_to_spot_id = {}
        self.index_to_user_id = {}
        self._init_mappings()
    
    def _init_mappings(self):
        """初始化ID到索引的映射"""
        # 加载所有景点
        spots = get_all_spots_from_db()
        
        # 为每个景点分配唯一索引
        for i, spot_id in enumerate(spots.keys()):
            self.spot_id_to_index[spot_id] = i
            self.index_to_spot_id[i] = spot_id
    
    def process_user_footprints(self, footprints):
        """处理用户足迹数据，构建用户-物品交互图"""
        # 为每个用户分配唯一索引
        user_indices = {}
        for user_id in footprints:
            if user_id not in self.user_id_to_index:
                self.user_id_to_index[user_id] = len(self.user_id_to_index)
                self.index_to_user_id[len(self.index_to_user_id)] = user_id
        
        # 构建边索引
        edges = []
        for user_id, user_spots in footprints.items():
            user_idx = self.user_id_to_index[user_id]
            for spot_id in user_spots:
                if spot_id in self.spot_id_to_index:
                    spot_idx = self.spot_id_to_index[spot_id]
                    # 用户到物品的边
                    edges.append([user_idx, len(self.user_id_to_index) + spot_idx])
                    # 物品到用户的边（无向图）
                    edges.append([len(self.user_id_to_index) + spot_idx, user_idx])
        
        # 转换为PyTorch张量
        edge_index = torch.tensor(edges, dtype=torch.long).t().contiguous()
        
        return edge_index
    
    def get_item_features(self):
        """获取所有物品的特征"""
        spot_features = feature_extractor.get_all_spot_features()
        num_items = len(self.spot_id_to_index)
        feature_dim = feature_extractor.get_feature_dim()
        
        # 初始化特征矩阵
        item_features = torch.zeros((num_items, feature_dim), dtype=torch.float32)
        
        # 填充特征
        for spot_id, features in spot_features.items():
            if spot_id in self.spot_id_to_index:
                idx = self.spot_id_to_index[spot_id]
                item_features[idx] = features
        
        return item_features
    
    def get_num_users(self):
        """获取用户数量"""
        return len(self.user_id_to_index)
    
    def get_num_items(self):
        """获取物品数量"""
        return len(self.spot_id_to_index)
    
    def user_id_to_idx(self, user_id):
        """将用户ID转换为索引"""
        return self.user_id_to_index.get(user_id, -1)
    
    def spot_id_to_idx(self, spot_id):
        """将景点ID转换为索引"""
        return self.spot_id_to_index.get(spot_id, -1)
    
    def idx_to_spot_id(self, idx):
        """将索引转换为景点ID"""
        return self.index_to_spot_id.get(idx, -1)
    
    def idx_to_user_id(self, idx):
        """将索引转换为用户ID"""
        return self.index_to_user_id.get(idx, -1)
    
    def generate_train_data(self, footprints):
        """生成训练数据"""
        # 处理用户足迹，构建边索引
        edge_index = self.process_user_footprints(footprints)
        
        # 获取物品特征
        item_features = self.get_item_features()
        
        # 创建数据对象
        data = Data(
            edge_index=edge_index,
            num_nodes=len(self.user_id_to_index) + len(self.spot_id_to_index)
        )
        
        return data, item_features

# 全局数据处理器实例
data_processor = DataProcessor()
