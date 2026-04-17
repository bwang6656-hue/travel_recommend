import numpy as np
from app.services.content_based_service import content_recommender
from app.services.neo4j_service import jaccard_similarity

class HybridRecommender:
    def __init__(self, cf_weight=0.5, content_weight=0.5):
        self.cf_weight = cf_weight
        self.content_weight = content_weight
    
    def recommend_by_hybrid(
        self,
        target_user,
        footprints,
        all_spots,
        top_k=10,
        cf_weight=None,
        content_weight=None
    ):
        """混合推荐（协同过滤 + 基于内容）"""
        if cf_weight is not None:
            self.cf_weight = cf_weight
        if content_weight is not None:
            self.content_weight = content_weight
        
        if self.cf_weight == 1.0:
            return self._collaborative_filtering_recommend(target_user, footprints, all_spots, top_k)
        elif self.content_weight == 1.0:
            return self._content_based_recommend(target_user, footprints, all_spots, top_k)
        else:
            return self._weighted_hybrid_recommend(target_user, footprints, all_spots, top_k)
    
    def _collaborative_filtering_recommend(self, target_user, footprints, all_spots, top_k):
        """纯协同过滤推荐"""
        target_spots = set(footprints.get(target_user, {}).keys())
        if not target_spots:
            return []
        
        similarities = []
        for user in footprints:
            if user != target_user:
                sim = jaccard_similarity(target_user, user, footprints)
                if sim > 0.1:
                    similarities.append((user, sim))
        
        similarities.sort(key=lambda x: x[1], reverse=True)
        similar_users = [u for u, _ in similarities[:10]]
        
        candidate_spots = set()
        for similar_user in similar_users:
            similar_spots = set(footprints.get(similar_user, {}).keys())
            candidate_spots.update(similar_spots - target_spots)
        
        cf_scores = {}
        for user, sim in similarities[:10]:
            user_spots = set(footprints.get(user, {}).keys())
            for spot_id in user_spots:
                if spot_id not in target_spots:
                    cf_scores[spot_id] = cf_scores.get(spot_id, 0) + sim
        
        candidate_with_score = []
        for spot_id in candidate_spots:
            if spot_id in all_spots:
                candidate_with_score.append({
                    "spot_id": spot_id,
                    "name": all_spots[spot_id]["name"],
                    "rating": all_spots[spot_id]["rating"],
                    "city": all_spots[spot_id]["city"],
                    "cf_score": cf_scores.get(spot_id, 0),
                    "content_score": 0.0,
                    "hybrid_score": cf_scores.get(spot_id, 0),
                    "reason": "与您相似的用户也喜欢"
                })
        
        candidate_with_score.sort(key=lambda x: x["hybrid_score"], reverse=True)
        return candidate_with_score[:top_k]
    
    def _content_based_recommend(self, target_user, footprints, all_spots, top_k):
        """纯基于内容推荐"""
        content_recs = content_recommender.recommend_by_content(
            target_user, footprints, all_spots, top_k
        )
        
        for rec in content_recs:
            rec["cf_score"] = 0.0
            rec["hybrid_score"] = rec["content_score"]
        
        return content_recs
    
    def _weighted_hybrid_recommend(self, target_user, footprints, all_spots, top_k):
        """加权混合推荐"""
        target_spots = set(footprints.get(target_user, {}).keys())
        
        cf_candidates = self._get_cf_candidates(target_user, footprints, all_spots)
        content_candidates = content_recommender.recommend_by_content(
            target_user, footprints, all_spots, top_k * 2
        )
        
        cf_scores = {rec["spot_id"]: rec["cf_score"] for rec in cf_candidates}
        content_scores = {rec["spot_id"]: rec["content_score"] for rec in content_candidates}
        
        all_candidate_ids = set(cf_scores.keys()) | set(content_scores.keys())
        
        max_cf_score = max(cf_scores.values()) if cf_scores else 1.0
        max_content_score = max(content_scores.values()) if content_scores else 1.0
        
        hybrid_results = []
        for spot_id in all_candidate_ids:
            if spot_id in all_spots and spot_id not in target_spots:
                cf_norm = cf_scores.get(spot_id, 0) / max_cf_score
                content_norm = content_scores.get(spot_id, 0) / max_content_score
                
                hybrid_score = self.cf_weight * cf_norm + self.content_weight * content_norm
                
                reason = self._generate_hybrid_reason(
                    spot_id, cf_norm, content_norm, all_spots
                )
                
                hybrid_results.append({
                    "spot_id": spot_id,
                    "name": all_spots[spot_id]["name"],
                    "rating": all_spots[spot_id]["rating"],
                    "city": all_spots[spot_id]["city"],
                    "cf_score": cf_scores.get(spot_id, 0),
                    "content_score": content_scores.get(spot_id, 0),
                    "hybrid_score": hybrid_score,
                    "reason": reason
                })
        
        hybrid_results.sort(key=lambda x: x["hybrid_score"], reverse=True)
        return hybrid_results[:top_k]
    
    def _get_cf_candidates(self, target_user, footprints, all_spots):
        """获取协同过滤候选景点"""
        target_spots = set(footprints.get(target_user, {}).keys())
        if not target_spots:
            return []
        
        similarities = []
        for user in footprints:
            if user != target_user:
                sim = jaccard_similarity(target_user, user, footprints)
                if sim > 0.1:
                    similarities.append((user, sim))
        
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        candidate_spots = set()
        cf_scores = {}
        for user, sim in similarities[:10]:
            user_spots = set(footprints.get(user, {}).keys())
            for spot_id in user_spots:
                if spot_id not in target_spots:
                    candidate_spots.add(spot_id)
                    cf_scores[spot_id] = cf_scores.get(spot_id, 0) + sim
        
        result = []
        for spot_id in candidate_spots:
            if spot_id in all_spots:
                result.append({
                    "spot_id": spot_id,
                    "cf_score": cf_scores.get(spot_id, 0)
                })
        
        return result
    
    def _generate_hybrid_reason(self, spot_id, cf_norm, content_norm, all_spots):
        """生成混合推荐理由"""
        reasons = []
        
        if cf_norm > 0.3:
            reasons.append("与您相似的用户也喜欢")
        elif content_norm > 0.5:
            reasons.append("非常符合您的偏好特征")
        elif content_norm > 0.3:
            reasons.append("符合您的偏好")
        
        spot = all_spots.get(spot_id, {})
        if spot.get("rating", 0) >= 4.5:
            reasons.append(f"评分较高 ({spot['rating']})")
        
        if not reasons:
            return "综合推荐"
        
        return "，".join(reasons)

hybrid_recommender = HybridRecommender(cf_weight=0.5, content_weight=0.5)
