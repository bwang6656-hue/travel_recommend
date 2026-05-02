from app.services.rag_service import rag_service
from app.services.vector_store_service import vector_store_service

print("=== 初始化向量存储 ===")
vector_store_service.build_index()

print("\n=== 测试RAG行程规划 ===")
result = rag_service.plan_itinerary("我想去北京玩3天，喜欢历史文化，预算不高")

print(f"\n查询: {result['query']}")
print(f"识别城市: {result.get('city')}")
print(f"识别天数: {result.get('days')}")
print(f"识别偏好: {result.get('preference')}")
print(f"相关景点数: {len(result.get('related_spots', []))}")
print(f"\n--- 行程方案 ---")
print(result['itinerary'][:500])
print("...")

print(f"\n--- 相关景点 ---")
for spot in result.get('related_spots', [])[:5]:
    print(f"  {spot['name']} ({spot['city']}) - 评分:{spot['rating']} 价格:{spot.get('price')}")
