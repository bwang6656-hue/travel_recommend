from app.services.neo4j_service import driver
from app.services.knowledge_graph_service import feature_extractor
from collections import defaultdict

class ExplanationGenerator:
    def __init__(self):
        pass
    
    def generate_explanation(self, user_id, recommended_spot_id, user_footprints, all_spots):
        """生成推荐解释"""
        # 获取用户历史足迹
        user_history = user_footprints.get(user_id, {})
        
        # 获取推荐景点信息
        recommended_spot = all_spots.get(recommended_spot_id, {})
        if not recommended_spot:
            return "基于您的历史偏好推荐"
        
        # 分析用户历史偏好
        city_preference = self._analyze_city_preference(user_history, all_spots)
        type_preference = self._analyze_type_preference(user_history, all_spots)
        
        # 生成解释
        explanations = []
        
        # 基于城市偏好的解释
        if city_preference:
            if recommended_spot.get("city") == city_preference:
                explanations.append(f"您经常访问{city_preference}的景点")
        
        # 基于类型偏好的解释
        if type_preference:
            if type_preference in recommended_spot.get("types", ""):
                explanations.append(f"您喜欢{type_preference}类型的景点")
        
        # 基于知识图谱的解释
        kg_explanation = self._generate_kg_explanation(recommended_spot_id)
        if kg_explanation:
            explanations.append(kg_explanation)
        
        # 基于评分的解释
        if recommended_spot.get("rating", 0) >= 4.5:
            explanations.append(f"该景点评分较高 ({recommended_spot['rating']})")
        
        # 如果没有特殊解释，返回默认解释
        if not explanations:
            return "基于您的历史偏好推荐"
        
        # 组合解释
        return "，".join(explanations) + "，因此为您推荐"
    
    def _analyze_city_preference(self, user_history, all_spots):
        """分析用户的城市偏好"""
        city_count = defaultdict(int)
        for spot_id in user_history:
            spot = all_spots.get(spot_id, {})
            city = spot.get("city", "")
            if city:
                city_count[city] += 1
        
        if city_count:
            return max(city_count, key=city_count.get)
        return None
    
    def _analyze_type_preference(self, user_history, all_spots):
        """分析用户的类型偏好"""
        type_count = defaultdict(int)
        for spot_id in user_history:
            spot = all_spots.get(spot_id, {})
            spot_type = spot.get("types", "")
            if spot_type:
                type_count[spot_type] += 1
        
        if type_count:
            return max(type_count, key=type_count.get)
        return None
    
    def _generate_kg_explanation(self, spot_id):
        """基于知识图谱生成解释"""
        with driver.session() as session:
            # 查找与推荐景点相似的已访问景点
            result = session.run("""
                MATCH (s:ScenicSpot {spot_id: $spot_id})
                OPTIONAL MATCH (s)-[:SAME_CATEGORY_AS]-(similar:ScenicSpot)
                RETURN similar.name AS similar_name
                LIMIT 1
            """, spot_id=spot_id)
            
            record = result.single()
            if record and record["similar_name"]:
                return f"与您可能喜欢的{record['similar_name']}属于同一类型"
        
        return None
    
    def generate_batch_explanations(self, user_id, recommended_spot_ids, user_footprints, all_spots):
        """批量生成推荐解释"""
        explanations = []
        for spot_id in recommended_spot_ids:
            explanation = self.generate_explanation(user_id, spot_id, user_footprints, all_spots)
            explanations.append(explanation)
        return explanations

# 全局解释生成器实例
explanation_generator = ExplanationGenerator()
