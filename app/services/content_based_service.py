import numpy as np
from collections import defaultdict
from sklearn.metrics.pairwise import cosine_similarity

class ContentBasedRecommender:
    def __init__(self):
        self.spot_features = {}
        self.city_mapping = {}
        self.type_mapping = {}
        self.feature_matrix = None
        self.spot_id_to_idx = {}
        self.idx_to_spot_id = {}
    
    def build_spot_features(self, all_spots):
        """构建景点特征"""
        cities = set()
        types = set()
        
        for spot_id, spot_info in all_spots.items():
            if spot_info.get("city"):
                cities.add(spot_info["city"])
            if spot_info.get("types"):
                types.add(spot_info["types"])
        
        self.city_mapping = {city: i for i, city in enumerate(cities)}
        self.type_mapping = {t: i for i, t in enumerate(types)}
        
        self.spot_id_to_idx = {}
        self.idx_to_spot_id = {}
        
        feature_dim = len(self.city_mapping) + len(self.type_mapping) + 1
        feature_list = []
        
        for i, (spot_id, spot_info) in enumerate(all_spots.items()):
            self.spot_id_to_idx[spot_id] = i
            self.idx_to_spot_id[i] = spot_id
            
            city = spot_info.get("city", "")
            spot_type = spot_info.get("types", "")
            rating = spot_info.get("rating", 0.0)
            
            city_vec = np.zeros(len(self.city_mapping))
            if city in self.city_mapping:
                city_vec[self.city_mapping[city]] = 1.0
            
            type_vec = np.zeros(len(self.type_mapping))
            if spot_type in self.type_mapping:
                type_vec[self.type_mapping[spot_type]] = 1.0
            
            rating_vec = np.array([rating / 5.0])
            
            features = np.concatenate([city_vec, type_vec, rating_vec])
            feature_list.append(features)
        
        self.feature_matrix = np.array(feature_list)
        return self.feature_matrix
    
    def build_user_profile(self, user_footprints, all_spots):
        """构建用户偏好向量"""
        if not user_footprints:
            return None
        
        visited_spots = []
        for spot_id in user_footprints.keys():
            if spot_id in self.spot_id_to_idx:
                visited_spots.append(self.spot_id_to_idx[spot_id])
        
        if not visited_spots:
            return None
        
        visited_features = self.feature_matrix[visited_spots]
        user_profile = np.mean(visited_features, axis=0)
        
        return user_profile
    
    def recommend_by_content(self, user_id, footprints, all_spots, top_k=10):
        """基于内容推荐景点"""
        if self.feature_matrix is None:
            self.build_spot_features(all_spots)
        
        user_profile = self.build_user_profile(footprints.get(user_id, {}), all_spots)
        if user_profile is None:
            return []
        
        visited_spot_ids = set(footprints.get(user_id, {}).keys())
        
        similarities = cosine_similarity([user_profile], self.feature_matrix)[0]
        
        candidate_indices = []
        for idx, spot_id in self.idx_to_spot_id.items():
            if spot_id not in visited_spot_ids:
                candidate_indices.append((idx, similarities[idx]))
        
        candidate_indices.sort(key=lambda x: x[1], reverse=True)
        
        recommendations = []
        for idx, score in candidate_indices[:top_k]:
            spot_id = self.idx_to_spot_id[idx]
            if spot_id in all_spots:
                recommendations.append({
                    "spot_id": spot_id,
                    "name": all_spots[spot_id]["name"],
                    "rating": all_spots[spot_id]["rating"],
                    "city": all_spots[spot_id]["city"],
                    "content_score": float(score),
                    "reason": self._generate_content_reason(spot_id, all_spots)
                })
        
        return recommendations
    
    def _generate_content_reason(self, spot_id, all_spots):
        """生成基于内容的推荐理由"""
        spot = all_spots.get(spot_id, {})
        reasons = []
        
        if spot.get("rating", 0) >= 4.5:
            reasons.append(f"该景点评分较高 ({spot['rating']})")
        
        if spot.get("city"):
            reasons.append(f"位于{spot['city']}")
        
        if spot.get("types"):
            reasons.append(f"属于{spot['types']}类型")
        
        return "，".join(reasons) if reasons else "符合您的偏好"
    
    def get_spot_similarity(self, spot_id1, spot_id2):
        """计算两个景点之间的相似度"""
        if spot_id1 not in self.spot_id_to_idx or spot_id2 not in self.spot_id_to_idx:
            return 0.0
        
        idx1 = self.spot_id_to_idx[spot_id1]
        idx2 = self.spot_id_to_idx[spot_id2]
        
        features1 = self.feature_matrix[idx1].reshape(1, -1)
        features2 = self.feature_matrix[idx2].reshape(1, -1)
        
        return cosine_similarity(features1, features2)[0][0]

content_recommender = ContentBasedRecommender()
