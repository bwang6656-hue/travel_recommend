from fastapi import APIRouter, HTTPException, Depends, Query, Body
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.schemas.schemas import RecommendationResponse, RecommendationItem, SpotDetail, CityRecommendationResponse, CityRecommendationItem, AITripRequest, AITripResponse
from app.services.neo4j_service import get_all_spots_from_db, get_user_footprints_from_mysql, recommend_by_footprint, extract_field, driver
from app.services.amap_service import get_city_weather
from app.services.ai_service import ai_trip_generator

router = APIRouter(prefix="/recommend", tags=["推荐"])

# 根据景点推荐
@router.get("", response_model=RecommendationResponse)
async def get_recommendations(
        spot_name: str = Query(..., description="景点名称，需完全匹配（例如 '外滩'、'故宫博物院'）"),
        limit: int = Query(10, ge=1, le=50, description="返回数量（1-50）"),
):
    all_spots = get_all_spots_from_db()
    target_spot = None
    target_spot_id = None
    # 按名称匹配景点
    for spot_id, spot_info in all_spots.items():
        if spot_info["name"] == spot_name:
            target_spot = spot_info
            target_spot_id = spot_id
            break
    if not target_spot:
        raise HTTPException(
            status_code=404,
            detail=f"景点名称 '{spot_name}' 不存在。请确认名称正确性",
        )
    with driver.session() as session:
        rec_result = session.run(
            """
            MATCH (target:ScenicSpot {name: $name})
            OPTIONAL MATCH (target)-[:IN_SAME_CITY_AS]-(c:ScenicSpot)
            OPTIONAL MATCH (target)-[:SAME_CATEGORY_AS]-(t:ScenicSpot)
            WITH target,
                 [x IN collect(c) WHERE x IS NOT NULL AND x <> target] AS city_recs,
                 [x IN collect(t) WHERE x IS NOT NULL AND x <> target] AS type_recs
            UNWIND (city_recs + type_recs) AS rec
            WITH DISTINCT rec, city_recs, type_recs
            WHERE rec.spot_id IS NOT NULL
            RETURN
                toInteger(rec.spot_id) AS spot_id,
                rec.name AS name,
                coalesce(rec.city, '') AS city,
                coalesce(toFloat(rec.rating), 0.0) AS rating,
                CASE WHEN rec IN city_recs THEN '同城' ELSE '同类' END AS reason
            ORDER BY rating DESC
            LIMIT $limit
            """,
            name=spot_name,
            limit=limit,
        )
        recommendations = []
        for record in rec_result:
            if record["spot_id"] is None:
                continue
            spot_id = extract_field(record["spot_id"], int, 0)
            name = extract_field(record["name"], str, "")
            city = extract_field(record["city"], str, "")
            rating = extract_field(record["rating"], float, 0.0)
            reason = extract_field(record["reason"], str, "")
            weather = get_city_weather(city)
            recommendations.append(RecommendationItem(
                spot_id=spot_id,
                name=name,
                city=city,
                rating=rating,
                reason=reason,
                weather=weather
            ))
        if not recommendations:
            raise HTTPException(status_code=404, detail="未找到相关推荐")
        return RecommendationResponse(
            target=f"景点 {spot_name}",
            count=len(recommendations),
            recommendations=recommendations,
        )

# 查看景点详情
@router.get("/spot/{spot_name}", response_model=SpotDetail)
async def get_spot_detail(spot_name: str):  # Path(..., description="景点名称，例如 '外滩'、'故宫博物院'")):
    all_spots = get_all_spots_from_db()
    target_spot_id = None

    for spot_id, spot_info in all_spots.items():
        if spot_info["name"] == spot_name:
            target_spot_id = spot_id
            break

    # 未找到匹配的景点
    if target_spot_id is None:
        raise HTTPException(status_code=404, detail=f"景点名称 '{spot_name}' 不存在，请确认名称正确性")

    # 组装并返回详情
    spot_info = all_spots[target_spot_id]
    return SpotDetail(
        spot_id=target_spot_id,
        name=spot_info["name"],
        city=spot_info["city"],
        rating=spot_info["rating"],
        address=spot_info["address"],
        types=spot_info["types"]
    )

# 根据城市推荐
@router.get("/city", response_model=CityRecommendationResponse)
async def get_city_recommendations(
        city: str = Query(..., description="城市名称，例如 '北京'、'上海'"),
        limit: int = Query(10, ge=1, le=50, description="返回数量（1-50）"),
):
    with driver.session() as session:
        rec_result = session.run(
            """
            MATCH (s:ScenicSpot)
            WHERE s.city = $city AND s.rating IS NOT NULL AND s.spot_id IS NOT NULL
            RETURN
                toInteger(s.spot_id) AS spot_id,
                s.name AS name,
                coalesce(s.city, '') AS city,
                coalesce(toFloat(s.rating), 0.0) AS rating
            ORDER BY rating DESC
            LIMIT $limit
            """,
            city=city,
            limit=limit,
        )
        recommendations = [
            CityRecommendationItem(
                spot_id=record["spot_id"],
                name=record["name"],
                city=record["city"],
                rating=record["rating"],
            )
            for record in rec_result
            if record["spot_id"] is not None
        ]
        if not recommendations:
            raise HTTPException(status_code=404, detail=f"城市 '{city}' 中未找到景点数据")
        return CityRecommendationResponse(
            city=city,
            count=len(recommendations),
            recommendations=recommendations,
        )

# 默认推荐
@router.get("/default", response_model=RecommendationResponse)
async def get_default_recommendations(
        limit: int = Query(10, ge=1, le=50, description="返回数量（1-50）"),
):
    all_spots = get_all_spots_from_db()
    default_spot_id = None
    default_spot_name = None
    # 优先找“外滩”作为默认景点
    for spot_id, info in all_spots.items():
        if info["name"] == "外滩":
            default_spot_id = spot_id
            default_spot_name = info["name"]
            break
    # 若无外滩，取评分最高的景点
    if default_spot_id is None:
        sorted_spots = sorted(all_spots.items(), key=lambda x: x[1]["rating"], reverse=True)
        if not sorted_spots:
            raise HTTPException(status_code=404, detail="数据库中没有可用的默认景点")
        default_spot_id = sorted_spots[0][0]
        default_spot_name = sorted_spots[0][1]["name"]
    with driver.session() as session:
        rec_result = session.run(
            """
            MATCH (target:ScenicSpot {spot_id: $spot_id})
            OPTIONAL MATCH (target)-[:IN_SAME_CITY_AS]-(c:ScenicSpot)
            OPTIONAL MATCH (target)-[:SAME_CATEGORY_AS]-(t:ScenicSpot)
            WITH target,
                 [x IN collect(c) WHERE x IS NOT NULL AND x <> target] AS city_recs,
                 [x IN collect(t) WHERE x IS NOT NULL AND x <> target] AS type_recs
            UNWIND (city_recs + type_recs) AS rec
            WITH DISTINCT rec, city_recs, type_recs
            WHERE rec.spot_id IS NOT NULL
            RETURN
                toInteger(rec.spot_id) AS spot_id,
                rec.name AS name,
                coalesce(rec.city, '') AS city,
                coalesce(toFloat(rec.rating), 0.0) AS rating,
                CASE WHEN rec IN city_recs THEN '同城' ELSE '同类' END AS reason
            ORDER BY rating DESC
            LIMIT $limit
            """,
            spot_id=default_spot_id,
            limit=limit,
        )
        recommendations = []
        for record in rec_result:
            if record["spot_id"] is None:
                continue
            spot_id = extract_field(record["spot_id"], int, 0)
            name = extract_field(record["name"], str, "")
            city = extract_field(record["city"], str, "")
            rating = extract_field(record["rating"], float, 0.0)
            reason = extract_field(record["reason"], str, "")
            # 添加weather字段
            weather = get_city_weather(city)
            recommendations.append(RecommendationItem(
                spot_id=spot_id,
                name=name,
                city=city,
                rating=rating,
                reason=reason,
                weather=weather
            ))
        if not recommendations:
            raise HTTPException(status_code=404, detail="未找到相关推荐")
        return RecommendationResponse(
            target=f"景点 {default_spot_name}",
            count=len(recommendations),
            recommendations=recommendations,
        )

# 根据用户足迹推荐
@router.get("/footprint", response_model=RecommendationResponse)
async def get_footprint_based_recommendations(
        user_id: int = Query(..., ge=1, description="用户ID"),
        limit: int = Query(10, ge=1, le=50, description="推荐数量（1-50）"),
        db: Session = Depends(get_db)
):
    all_spots = get_all_spots_from_db()
    user_footprints = get_user_footprints_from_mysql(db)
    if not all_spots:
        raise HTTPException(status_code=404, detail="Neo4j中无有效景点数据")
    if user_id not in user_footprints:
        raise HTTPException(status_code=404, detail="该用户暂无足迹数据，请先添加足迹")
    try:
        raw_recs = recommend_by_footprint(user_id, user_footprints, all_spots, top_k=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"推荐算法执行失败: {str(e)}")
    if not raw_recs:
        raise HTTPException(status_code=404, detail="未找到相似用户，暂无推荐结果")
    recommendations = [
        RecommendationItem(
            spot_id=rec["spot_id"],
            name=rec["name"],
            city=rec["city"],
            rating=round(rec["rating"], 2),
            reason="基于您的出行足迹推荐",
            weather=get_city_weather(rec["city"])
        )
        for rec in raw_recs
    ]
    return RecommendationResponse(
        target=f"用户{user_id}",
        count=len(recommendations),
        recommendations=recommendations
    )

# AI个性化推荐
@router.post("/ai", response_model=AITripResponse, summary="AI生成行程推荐文案")
async def generate_ai_itinerary(
        request: AITripRequest = Body(..., description="行程生成参数")
):
    # 参数校验
    if not request.spots:
        raise HTTPException(status_code=400, detail="景点列表不能为空")

    for spot in request.spots:
            if not spot.get("name") or not spot.get("city"):
                raise HTTPException(
                    status_code=400,
                    detail=f"景点信息不完整：缺少name或city字段（当前景点：{spot}")

    # 调用AI工具生成行程
    try:
        itinerary = ai_trip_generator.generate_itinerary(
            spots=request.spots,
            days=request.days,
            preference=request.preference
        )
        return AITripResponse(
            itinerary=itinerary,
            days=request.days,
            preference=request.preference
        )
    except Exception as ext:
        raise HTTPException(status_code=500, detail=f"生成行程失败：{str(ext)[:50]}")
