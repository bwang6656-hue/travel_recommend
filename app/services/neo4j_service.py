from neo4j import GraphDatabase
from collections import defaultdict
from app.config.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

# 创建 Neo4j 驱动
if not NEO4J_PASSWORD:
    raise RuntimeError("请在 .env 文件中设置 NEO4J_PASSWORD")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# 全局缓存
_cached_all_spots = None  # {spot_id(int): {"name": str, "rating": float, "city": str, "address": str, "types": str}}
_cached_user_footprints = None  # {user_id: {spot_id(int): True}}

def get_all_spots_from_db():
    """从 Neo4j 获取所有景点数据"""
    global _cached_all_spots
    if _cached_all_spots is None:
        with driver.session() as session:
            result = session.run("""
                MATCH (s:ScenicSpot)
                WHERE s.spot_id IS NOT NULL AND s.name IS NOT NULL AND s.rating IS NOT NULL
                RETURN 
                    toInteger(s.spot_id) AS spot_id,
                    s.name AS name,
                    toFloat(s.rating) AS rating,
                    coalesce(s.city, '') AS city,
                    coalesce(s.address, '') AS address,
                    coalesce(s.type, '') AS types
            """)
            spot_data = {}
            for record in result:
                spot_id = record["spot_id"]
                if spot_id is None:
                    print(f"⚠️  景点 {record['name']} 缺少spot_id属性，已跳过")
                    continue
                spot_data[spot_id] = {
                    "name": record["name"],
                    "rating": record["rating"],
                    "city": record["city"],
                    "address": record["address"],
                    "types": record["types"]
                }
            if not spot_data:
                raise RuntimeError("Neo4j中无有效景点数据（需为ScenicSpot节点添加唯一的spot_id属性）")
            _cached_all_spots = spot_data
    return _cached_all_spots

def get_user_footprints_from_mysql(db):
    """从 MySQL 获取用户足迹数据"""
    global _cached_user_footprints
    if _cached_user_footprints is None:
        try:
            from sqlalchemy import text
            result = db.execute(text("SELECT user_id, spot_id, visit_time FROM user_footprint WHERE spot_id IS NOT NULL"))
            footprints = defaultdict(dict)
            for user_id, spot_id, visit_time in result:
                footprints[user_id][spot_id] = True
            _cached_user_footprints = dict(footprints)
        except Exception as e:
            if "user_footprint" in str(e):
                raise RuntimeError(f"MySQL中缺少user_footprint表，请先执行创建表SQL：{e}")
            else:
                raise RuntimeError(f"从MySQL加载用户足迹失败：{e}")
    return _cached_user_footprints

def clear_footprint_cache():
    """清除用户足迹缓存"""
    global _cached_user_footprints
    _cached_user_footprints = None

def jaccard_similarity(user1, user2, footprints):
    """计算不同用户足迹的杰卡德系数"""
    user1_spots = set(footprints.get(user1, {}).keys())
    user2_spots = set(footprints.get(user2, {}).keys())
    if len(user1_spots) == 0 or len(user2_spots) == 0:
        return 0.0
    intersection = len(user1_spots & user2_spots)
    union = len(user1_spots | user2_spots)
    return intersection / union if union > 0 else 0.0

def recommend_by_footprint(target_user, footprints, all_spots, top_k=10):
    """基于用户足迹推荐景点"""
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
    candidate_with_rating = []
    for spot_id in candidate_spots:
        if spot_id in all_spots:
            candidate_with_rating.append({
                "spot_id": spot_id,
                "name": all_spots[spot_id]["name"],
                "rating": all_spots[spot_id]["rating"],
                "city": all_spots[spot_id]["city"]
            })
    candidate_with_rating.sort(key=lambda x: x["rating"], reverse=True)
    return candidate_with_rating[:top_k]

def extract_field(raw_value, target_type, default=None):
    """提取字段值并进行类型转换"""
    if isinstance(raw_value, tuple):
        raw_value = raw_value[0] if len(raw_value) > 0 else default
    # 空值兜底 + 类型强制转换
    try:
        return target_type(raw_value) if raw_value is not None else default
    except (ValueError, TypeError):
        return default

def close_neo4j_driver():
    """关闭 Neo4j 驱动"""
    driver.close()
