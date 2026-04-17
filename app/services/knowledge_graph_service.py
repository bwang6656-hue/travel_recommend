from app.services.neo4j_service import driver
import torch
import numpy as np
from collections import defaultdict

class KnowledgeGraphFeatureExtractor:
    def __init__(self):
        self.city_encoder = None
        self.type_encoder = None
        self.city_mapping = {}
        self.type_mapping = {}
        self._init_encoders()
    
    def _init_encoders(self):
        """初始化城市和类型的编码器"""
        cities = set()
        types = set()
        
        # 从Neo4j获取所有城市和类型信息
        with driver.session() as session:
            result = session.run("""
                MATCH (s:ScenicSpot)
                WHERE s.city IS NOT NULL AND s.type IS NOT NULL
                RETURN DISTINCT s.city AS city, s.type AS type
            """)
            
            for record in result:
                if record["city"]:
                    cities.add(record["city"])
                if record["type"]:
                    types.add(record["type"])
        
        # 创建城市映射
        self.city_mapping = {city: i for i, city in enumerate(cities)}
        self.city_encoder = len(self.city_mapping)
        
        # 创建类型映射
        type_list = list(types)
        self.type_mapping = {t: i for i, t in enumerate(type_list)}
        self.type_encoder = len(self.type_mapping)
    
    def get_spot_features(self, spot_id):
        """获取景点的特征向量"""
        with driver.session() as session:
            result = session.run("""
                MATCH (s:ScenicSpot {spot_id: $spot_id})
                RETURN s.city AS city, s.type AS type, s.rating AS rating
            """, spot_id=spot_id)
            
            record = result.single()
            if not record:
                return None
            
            # 提取特征
            city = record["city"] or ""
            spot_type = record["type"] or ""
            rating = float(record["rating"]) if record["rating"] else 0.0
            
            # 城市编码
            city_idx = self.city_mapping.get(city, len(self.city_mapping))
            city_one_hot = np.zeros(self.city_encoder + 1)
            city_one_hot[city_idx] = 1.0
            
            # 类型编码
            type_idx = self.type_mapping.get(spot_type, len(self.type_mapping))
            type_one_hot = np.zeros(self.type_encoder + 1)
            type_one_hot[type_idx] = 1.0
            
            # 归一化评分
            normalized_rating = rating / 5.0  # 假设评分范围是0-5
            
            # 组合特征
            features = np.concatenate([
                city_one_hot,
                type_one_hot,
                np.array([normalized_rating])
            ])
            
            return torch.tensor(features, dtype=torch.float32)
    
    def get_all_spot_features(self):
        """获取所有景点的特征向量"""
        spot_features = {}
        
        with driver.session() as session:
            result = session.run("""
                MATCH (s:ScenicSpot)
                WHERE s.spot_id IS NOT NULL
                RETURN toInteger(s.spot_id) AS spot_id, s.city AS city, s.type AS type, s.rating AS rating
            """)
            
            for record in result:
                spot_id = record["spot_id"]
                city = record["city"] or ""
                spot_type = record["type"] or ""
                rating = float(record["rating"]) if record["rating"] else 0.0
                
                # 城市编码
                city_idx = self.city_mapping.get(city, len(self.city_mapping))
                city_one_hot = np.zeros(self.city_encoder + 1)
                city_one_hot[city_idx] = 1.0
                
                # 类型编码
                type_idx = self.type_mapping.get(spot_type, len(self.type_mapping))
                type_one_hot = np.zeros(self.type_encoder + 1)
                type_one_hot[type_idx] = 1.0
                
                # 归一化评分
                normalized_rating = rating / 5.0
                
                # 组合特征
                features = np.concatenate([
                    city_one_hot,
                    type_one_hot,
                    np.array([normalized_rating])
                ])
                
                spot_features[spot_id] = torch.tensor(features, dtype=torch.float32)
        
        return spot_features
    
    def get_feature_dim(self):
        """获取特征向量的维度"""
        return (self.city_encoder + 1) + (self.type_encoder + 1) + 1

# 全局特征提取器实例
feature_extractor = KnowledgeGraphFeatureExtractor()
