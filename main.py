from fastapi import FastAPI, HTTPException, Query, Depends, Path, Body
from fastapi.middleware.cors import CORSMiddleware
from neo4j import GraphDatabase
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any
import os
from collections import defaultdict
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, Column, Integer, String, DECIMAL, Float, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from passlib.context import CryptContext
from contextlib import asynccontextmanager
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning
import time
from utils.ai_utils import ai_trip_generator
from datetime import datetime

# 加载环境变量
load_dotenv()
# 禁用SSL警告（仅测试用，生产环境建议配置证书）
disable_warnings(InsecureRequestWarning)

# === 全局变量：高德接口配置 ===
_amap_session = None
_weather_cache = {}
_CACHE_EXPIRE = 36000
_city_request_timer = {}
_MOCK_WEATHER_DATA = {
    "北京": {"temperature": "5℃", "weather": "晴", "wind": "北风2级", "humidity": "30%"},
    "上海": {"temperature": "10℃", "weather": "多云", "wind": "东风3级", "humidity": "60%"},
    "广州": {"temperature": "18℃", "weather": "阴", "wind": "南风1级", "humidity": "75%"},
    "深圳": {"temperature": "16℃", "weather": "小雨", "wind": "东南风2级", "humidity": "80%"},
    "杭州": {"temperature": "8℃", "weather": "晴转多云", "wind": "西北风2级", "humidity": "50%"},
    "成都": {"temperature": "12℃", "weather": "阴", "wind": "东北风1级", "humidity": "70%"},
    "重庆": {"temperature": "11℃", "weather": "小雨", "wind": "西南风2级", "humidity": "85%"},
    "西安": {"temperature": "3℃", "weather": "晴", "wind": "西风2级", "humidity": "40%"},
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动逻辑：验证数据库连接+初始化缓存
    try:
        # 验证 Neo4j 连接
        driver.verify_connectivity()
        # 验证 MySQL 连接
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        # 预加载缓存
        get_all_spots_from_db()
        get_user_footprints_from_mysql()
        print("✅ Neo4j + MySQL 连接成功，缓存初始化完成")
    except Exception as e:
        raise RuntimeError(f"启动失败：{e}")

    yield  # 服务运行中

    # 关闭逻辑
    driver.close()
    # 关闭高德接口会话
    global _amap_session
    if _amap_session:
        _amap_session.close()
    print("🔌 数据库连接已关闭")

# === FastAPI 基础配置（绑定lifespan） ===
app = FastAPI(
    title="智能旅游景点推荐系统",
    version="2.4.0",
    lifespan=lifespan  # 绑定生命周期事件
)

# === CORS 跨域配置 ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === 密码加密配置 ===
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# === Neo4j 连接配置 ===
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

if not NEO4J_PASSWORD:
    raise RuntimeError("请在 .env 文件中设置 NEO4J_PASSWORD")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# === MySQL 配置 ===
SQLALCHEMY_DATABASE_URL = os.getenv(
    "MYSQL_URL",
    "mysql+pymysql://root:zxzdxc86@localhost:3306/travel"
)
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# === ORM 模型 ===
class DBUser(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    password = Column(String(255), nullable=False)

class DBHotel(Base):
    __tablename__ = "hotel"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, comment="酒店名")
    city = Column(String(255), nullable=False, comment="城市")
    price = Column(DECIMAL(10, 2), nullable=False, comment="价格")
    phone = Column(String(255), nullable=True, comment="联系方式")
    rate = Column(Float, nullable=False, comment="评分")

class DBFood(Base):
    __tablename__ = "food"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, comment="店名")
    type = Column(String(255), nullable=False, comment="食物类型")
    phone = Column(String(255), nullable=True, comment="联系电话")
    city = Column(String(255), nullable=False, comment="所处城市")
    rate = Column(Float, nullable=False, comment="评分")

class DBFootprint(Base):
    __tablename__ = "user_footprint"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer,nullable=False, comment="用户ID")
    spot_id = Column(Integer, nullable=False, comment="景点ID")
    visit_time = Column(DateTime, default=datetime.now, comment="访问时间")

try:
    Base.metadata.reflect(bind=engine)
except Exception as e:
    print(f"⚠️  MySQL 表映射警告: {e}")

# === 依赖函数：获取 MySQL 数据库会话 ===
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# === 全局缓存 ===
_cached_all_spots = None  # {spot_id(int): {"name": str, "rating": float, "city": str, "address": str, "types": str}}
_cached_user_footprints = None  # {user_id: {spot_id(int): True}}

# Pydantic模型
# 用户相关模型
class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, description="用户名（必填，3位以上）")
    password: str = Field(..., min_length=6, description="密码（必填，6位以上）")
    email: Optional[EmailStr] = Field(None, description="邮箱（可选，不要求唯一）")

class UserLoginRequest(BaseModel):
    username: str = Field(..., description="用户名（必填）")
    password: str = Field(..., description="密码（必填）")

class UserInfoResponse(BaseModel):
    id: int
    username: str
    email: Optional[str]

class UserUpdateRequest(BaseModel):
    email: Optional[EmailStr] = Field(None, description="邮箱（可选，不要求唯一）")
    password: Optional[str] = Field(None, min_length=6, description="新密码（可选，6位以上）")

class FootprintRequest(BaseModel):
    user_id: int = Field(..., ge=1, description="用户ID")
    spot_id: int = Field(..., ge=1, description="景点ID")

class FootprintResponse(BaseModel):
    id: int
    user_id: int
    spot_id: int
    visit_time: datetime
    class Config:
        from_attributes = True

class FootprintListResponse(BaseModel):
    user_id: int
    count: int
    footprints: List[FootprintResponse]

class DeleteSuccessResponse(BaseModel):
    status: str
    detail: str

# 推荐相关模型
class RecommendationItem(BaseModel):
    spot_id: int
    name: str
    city: str
    rating: float
    reason: str
    weather: Optional[Dict[str, str]] = Field(None, description="景点所在城市实时天气")

class SpotDetail(BaseModel):
    spot_id: int
    name: str
    city: str
    rating: float
    address: str
    types: str

class CityRecommendationItem(BaseModel):
    spot_id: int
    name: str
    city: str
    rating: float

class RecommendationResponse(BaseModel):
    target: str
    count: int
    recommendations: List[RecommendationItem]

class CityRecommendationResponse(BaseModel):
    city: str
    count: int
    recommendations: List[CityRecommendationItem]

class HotelItem(BaseModel):
    id: int
    name: str
    city: str
    price: float
    phone: Optional[str]
    rate: float

class HotelListResponse(BaseModel):
    city: str
    count: int
    hotels: List[HotelItem]

class FoodItem(BaseModel):
    id: int
    name: str
    type: str
    city: str
    phone: Optional[str]
    rate: float

class FoodListResponse(BaseModel):
    city: str
    type: str
    count: int
    foods: List[FoodItem]

# AI行程相关模型
class AITripRequest(BaseModel):
    spots: List[Dict[str, Any]] = Field(..., description="景点列表（含name/city/type字段）")
    days: int = Field(1, ge=1, le=3, description="行程天数（1-3天）")
    preference: Optional[str] = Field(None, description="游玩偏好（如美食优先、休闲放松）")

class AITripResponse(BaseModel):
    itinerary: str = Field(..., description="自然语言行程文案")
    days: int = Field(..., description="行程天数")
    preference: Optional[str] = Field(None, description="游玩偏好")

# === 工具函数（密码加密/验证） ===
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码和加密密码是否匹配"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """生成密码的加密哈希值"""
    return pwd_context.hash(password)

# === 重构高德接口函数 ===
def _init_amap_session():
    """初始化高德接口会话（连接池+重试+HTTP/1.1）"""
    global _amap_session
    if _amap_session:
        return _amap_session

    session = requests.Session()
    # 配置重试策略：3次重试，间隔1秒
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        allowed_methods=["GET"],
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=10,
        pool_maxsize=10,
        pool_block=False
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    # 强制HTTP/1.1，解决HTTP/2兼容问题
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "keep-alive"
    })
    session.timeout = 5  # 5秒超时
    session.verify = False  # 临时关闭SSL验证（解决SSL错误）

    _amap_session = session
    return session

def _check_request_frequency(city: str):
    """控制请求频率，避免高频调用高德接口"""
    now = time.time()
    if city in _city_request_timer:
        last_time = _city_request_timer[city]
        if now - last_time < 2:  # 间隔至少2秒
            time.sleep(2 - (now - last_time))
    _city_request_timer[city] = now

def get_city_adcode(city: str) -> Optional[str]:
    """获取城市adcode（添加缓存+重试+频率控制）"""
    if not city:
        return None

    amap_key = os.getenv("AMAP_KEY")
    amap_district_url = os.getenv("AMAP_DISTRICT_URL")
    if not amap_key or not amap_district_url:
        print("未配置高德API Key/行政区划查询URL")
        return None

    # 频率控制
    _check_request_frequency(city)

    try:
        session = _init_amap_session()
        response = session.get(
            url=amap_district_url,
            params={
                "keywords": city.strip(),
                "key": amap_key,
                "subdistrict": 0,
                "extensions": "base",
                "output": "json"
            }
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "1":
            print(f"高德行政区划接口返回错误：{data.get('info')}")
            return None

        districts = data.get("districts", [])
        if not districts:
            print(f"未找到城市「{city}」的行政区划编码")
            return None

        return districts[0].get("adcode")
    except requests.exceptions.Timeout:
        print(f"[错误] 高德行政区划接口超时（城市：{city}）")
        return None
    except requests.exceptions.ConnectionResetError as e:
        print(f"[错误] 高德接口连接被重置（城市:{city}）：{str(e)}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"[错误] 高德行政区划接口请求失败（城市：{city}）：{str(e)}")
        return None
    except Exception as e:
        print(f"[错误] 解析行政区划数据失败（城市：{city}）：{str(e)}")
        return None

def get_city_weather(city: str) -> Optional[Dict[str, str]]:
    """获取城市天气（添加缓存+兜底模拟数据）"""
    # 1. 先查缓存
    if city in _weather_cache:
        cache_data, cache_time = _weather_cache[city]
        if time.time() - cache_time < _CACHE_EXPIRE:
            return cache_data

    # 2. 尝试调用高德接口
    adcode = get_city_adcode(city)
    amap_key = os.getenv("AMAP_KEY")
    amap_weather_url = os.getenv("AMAP_WEATHER_URL")
    weather_data = None

    if adcode and amap_key and amap_weather_url:
        try:
            session = _init_amap_session()
            response = session.get(
                url=amap_weather_url,
                params={
                    "key": amap_key,
                    "city": adcode,
                    "extensions": "base",
                    "output": "json"
                }
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "1" and data.get("lives"):
                live = data["lives"][0]
                weather_data = {
                    "temperature": f"{live.get('temperature', '未知')}℃",
                    "weather": live.get("weather", "未知"),
                    "wind": f"{live.get('winddirection', '未知')}{live.get('windpower', '')}级",
                    "humidity": f"{live.get('humidity', '未知')}%"
                }
        except requests.exceptions.Timeout:
            print(f"[错误] 高德天气接口超时（城市：{city}）")
        except requests.exceptions.ConnectionResetError as e:
            print(f"[错误] 高德天气接口连接被重置（城市：{city}）：{str(e)}")
        except requests.exceptions.RequestException as e:
            print(f"[错误] 高德天气接口请求失败（城市：{city}）：{str(e)}")
        except Exception as e:
            print(f"[错误] 解析天气数据失败（城市：{city}）：{str(e)}")

    # 3. 高德接口失败，使用模拟数据兜底
    if not weather_data:
        weather_data = _MOCK_WEATHER_DATA.get(city, {
            "temperature": "未知",
            "weather": "未知",
            "wind": "未知",
            "humidity": "未知%"
        })

    # 4. 写入缓存
    _weather_cache[city] = (weather_data, time.time())
    # 缓存超过100条时清理
    if len(_weather_cache) > 100:
        _weather_cache.clear()

    return weather_data

def get_all_spots_from_db():
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

def get_user_footprints_from_mysql():
    global _cached_user_footprints
    if _cached_user_footprints is None:
        db = SessionLocal()
        try:
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
        finally:
            db.close()
    return _cached_user_footprints

# 计算不同用户足迹的杰卡德系数
def jaccard_similarity(user1, user2, footprints):
    user1_spots = set(footprints.get(user1, {}).keys())
    user2_spots = set(footprints.get(user2, {}).keys())
    if len(user1_spots) == 0 or len(user2_spots) == 0:
        return 0.0
    intersection = len(user1_spots & user2_spots)
    union = len(user1_spots | user2_spots)
    return intersection / union if union > 0 else 0.0

def recommend_by_footprint(target_user, footprints, all_spots, top_k=10):
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

def extract_field(raw_value, target_type: type, default=None):
    if isinstance(raw_value, tuple):
        raw_value = raw_value[0] if len(raw_value) > 0 else default
    # 空值兜底 + 类型强制转换
    try:
        return target_type(raw_value) if raw_value is not None else default
    except (ValueError, TypeError):
        return default

# 根据景点推荐
@app.get("/recommend", response_model=RecommendationResponse)
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
@app.get("/spot/{spot_name}", response_model=SpotDetail)
async def get_spot_detail(spot_name: str = Path(..., description="景点名称，例如 '外滩'、'故宫博物院'")):
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
@app.get("/recommend/city", response_model=CityRecommendationResponse)
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
@app.get("/recommend/default", response_model=RecommendationResponse)
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

# 健康检查
@app.get("/health")
async def health_check():
    try:
        driver.verify_connectivity()
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return {
            "status": "ok",
            "neo4j_connected": True,
            "mysql_connected": True
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={"status": "degraded", "error": str(e)},
        )

# 获取所有景点
@app.get("/spots", response_model=List[SpotDetail])
def get_all_spots():
    all_spots= get_all_spots_from_db()
    spot_list = []
    for spot_id, spot_info in all_spots.items():
        spot_list.append(SpotDetail(
            spot_id=spot_id,
            name=spot_info["name"],
            city=spot_info["city"],
            rating=spot_info["rating"],
            address=spot_info["address"],
            types=spot_info["types"]
        ))
    return spot_list

# 添加用户足迹
@app.post("/user/footprints", response_model=FootprintResponse)
def add_user_footprint(
        footprint_data:FootprintRequest=Body(..., description="用户足迹"),
        db=Depends(get_db)
):
    try:
        user_exists = db.query(DBUser).filter(DBUser.id == footprint_data.user_id).first()
        if not user_exists:
            raise HTTPException(status_code=404, detail=f"用户ID {footprint_data.user_id} 不存在")
        all_spots = get_all_spots_from_db()
        if footprint_data.spot_id not in all_spots:
            raise HTTPException(status_code=404, detail=f"景点ID {footprint_data.spot_id} 不存在")

        #避免重复添加
        existing_footprint = db.query(DBFootprint).filter(
            DBFootprint.user_id == footprint_data.user_id,
            DBFootprint.spot_id == footprint_data.spot_id
        ).first()
        if existing_footprint:
            raise HTTPException(status_code=400, detail="该足迹已存在，无需重复添加")

        new_footprint = DBFootprint(
            user_id=footprint_data.user_id,
            spot_id=footprint_data.spot_id,
            visit_time=datetime.now()
        )
        db.add(new_footprint)
        db.commit()
        db.refresh(new_footprint)

        global _cached_user_footprints
        _cached_user_footprints = None
        get_user_footprints_from_mysql()
        return new_footprint
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"添加足迹失败：{str(e)}")
        raise HTTPException(status_code=500, detail=f"添加足迹失败:{str(e)}")

# 获取用户足迹
@app.get("/user/footprints", response_model=FootprintListResponse)
def get_user_footprints(
        user_id: int = Query(...,ge=1, description="用户ID "),
        db=Depends(get_db)
):
    try:
        #查询该用户所有足迹（按时间访问倒序）
        footprints_orm = db.query(DBFootprint).filter(DBFootprint.user_id == user_id).order_by(
            DBFootprint.visit_time.desc()).all()
        footprints = [FootprintResponse.model_validate(fp) for fp in footprints_orm]
        return FootprintListResponse(
            user_id=user_id,
            count=len(footprints),
            footprints= footprints
        )
    except Exception as e:
        print(f"获取足迹失败{str(e)}")
        raise HTTPException(status_code=500, detail=f"获取足迹失败{str(e)}")

# 删除用户足迹
@app.delete("/user/footprints", response_model=DeleteSuccessResponse)
def delete_user_footprints(
        footprint_data:FootprintRequest = Body(..., description="用户足迹"),
        db= Depends(get_db)
):
    try:
        #检验用户存在
        user_exist = db.query(DBUser).filter(DBUser.id == footprint_data.user_id).first()
        if not user_exist:
            raise HTTPException(status_code=404, detail=f"用户ID {footprint_data.user_id} 不存在")

        #检验足迹存在
        exist_footprint = db.query(DBFootprint).filter(
            DBFootprint.user_id == footprint_data.user_id,
            DBFootprint.spot_id == footprint_data.spot_id
        ).first()
        if not exist_footprint:
            raise HTTPException(status_code=404, detail=f"该足迹不存在")
        db.delete(exist_footprint)
        db.commit()

        global _cached_user_footprints
        _cached_user_footprints = None
        get_user_footprints_from_mysql()
        return {"status": "ok", "detail": "足迹删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"足迹删除失败{str(e)}")
        raise HTTPException(status_code=500, detail=f"用户足迹删除失败{str(e)}")

# 根据用户足迹推荐
@app.get("/recommend/footprint", response_model=RecommendationResponse)
async def get_footprint_based_recommendations(
        user_id: int = Query(..., ge=1, description="用户ID"),
        limit: int = Query(10, ge=1, le=50, description="推荐数量（1-50）"),
):
    all_spots = get_all_spots_from_db()
    user_footprints = get_user_footprints_from_mysql()
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
@app.post("/recommend/ai", response_model=AITripResponse, summary="AI生成行程推荐文案")
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
                detail=f"景点信息不完整：缺少name或city字段（当前景点：{spot}）"
            )

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

# 用户注册
@app.post("/auth/register", response_model=UserInfoResponse, summary="用户注册")
def user_register(
        user_data: UserRegisterRequest,
        db=Depends(get_db)
):
    try:
        existing_user = db.query(DBUser).filter(DBUser.username == user_data.username).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="用户名已被注册")

        hashed_password = get_password_hash(user_data.password)
        new_user = DBUser(
            username=user_data.username,
            password=hashed_password,
            email=user_data.email
        )

        # 保存到数据库
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        # 返回用户信息（不含密码）
        return UserInfoResponse(
            id=new_user.id,
            username=new_user.username,
            email=new_user.email
        )
    except HTTPException:
        raise  # 主动抛出的业务异常直接返回
    except Exception as e:
        db.rollback()  # 数据库操作异常回滚
        print(f"注册接口报错：{str(e)}")
        raise HTTPException(status_code=500, detail=f"注册失败：{str(e)}")

# 用户登录
@app.post("/auth/login", response_model=UserInfoResponse, summary="用户登录")
def user_login(
        login_data: UserLoginRequest,
        db=Depends(get_db)
):
    try:
        user = db.query(DBUser).filter(DBUser.username == login_data.username).first()
        if not user:
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        if not verify_password(login_data.password, user.password):
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        return UserInfoResponse(
            id=user.id,
            username=user.username,
            email=user.email
        )
    except HTTPException:
        raise  # 主动抛出的业务异常直接返回
    except Exception as e:
        print(f"登录接口报错：{str(e)}")
        raise HTTPException(status_code=500, detail=f"登录失败：{str(e)}")

# 获取用户信息
@app.get("/user/{user_id}", response_model=UserInfoResponse, summary="获取用户信息")
def get_user_info(
        user_id: int = Path(..., ge=1, description="用户ID（users表的id）"),
        db=Depends(get_db)
):
    try:
        # 根据ID查找用户
        user = db.query(DBUser).filter(DBUser.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        # 返回用户信息
        return UserInfoResponse(
            id=user.id,
            username=user.username,
            email=user.email
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"获取用户信息报错：{str(e)}")
        raise HTTPException(status_code=500, detail=f"获取用户信息失败：{str(e)}")

# 修改用户信息
@app.put("/user/{user_id}", response_model=UserInfoResponse, summary="修改用户信息")
def update_user_info(
        user_id: int = Path(..., ge=1, description="用户ID（users表的id）"),
        update_data: UserUpdateRequest = Body(...),
        db=Depends(get_db)
):
    try:
        # 根据ID查找用户
        user = db.query(DBUser).filter(DBUser.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        # 更新字段
        if update_data.email is not None:
            user.email = update_data.email
        if update_data.password is not None:
            user.password = get_password_hash(update_data.password)

        db.commit()
        db.refresh(user)

        return UserInfoResponse(
            id=user.id,
            username=user.username,
            email=user.email
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"修改用户信息报错：{str(e)}")
        raise HTTPException(status_code=500, detail=f"修改用户信息失败：{str(e)}")

# 酒店查询
@app.get("/hotel", response_model=HotelListResponse, summary="酒店查询")
def get_hotel_list(
        city: str = Query(..., description="城市名称，例如 '北京'、'上海'"),
        sort_by: str = Query("price", description="排序字段，可选 price（价格）、rating（评分）"),
        sort_order: str = Query("asc", description="排序方向，可选 asc（升序）、desc（降序）"),
        db=Depends(get_db)
):
    try:
        sort_field = DBHotel.price if sort_by == "price" else DBHotel.rate
        if sort_order == "desc":
            sort_field = sort_field.desc()

        hotel_orm_list = db.query(DBHotel).filter(DBHotel.city == city).order_by(sort_field).all()
        if not hotel_orm_list:
            raise HTTPException(status_code=404, detail=f"城市「{city}」暂无酒店数据")

        hotels = [
            HotelItem(
                id=hotel.id,
                name=hotel.name,
                city=hotel.city,
                price=float(hotel.price),
                phone=hotel.phone,
                rate=hotel.rate
            )
            for hotel in hotel_orm_list
        ]

        return HotelListResponse(
            city=city,
            count=len(hotels),
            hotels=hotels
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"酒店查询异常：{str(e)}")
        raise HTTPException(status_code=500, detail=f"酒店查询失败：{str(e)}")

# 美食查询
@app.get("/food", response_model=FoodListResponse, summary="按城市+类型查询美食（支持排序）")
def get_food_list(
        city: str = Query(..., description="城市名称，例如 '北京'、'上海'"),
        type: str = Query(..., description="食物类型，可选 地方菜系、火锅烧烤、小吃快餐"),
        sort_order: str = Query("desc", description="排序方向，可选 asc（升序）、desc（降序）"),
        db=Depends(get_db)
):
    try:
        sort_field = DBFood.rate.desc() if sort_order == "desc" else DBFood.rate.asc()

        food_orm_list = db.query(DBFood).filter(DBFood.city == city, DBFood.type == type).order_by(sort_field).all()
        if not food_orm_list:
            raise HTTPException(status_code=404, detail=f"城市「{city}」暂无类型为「{type}」的美食数据")

        foods = [
            FoodItem(
                id=food.id,
                name=food.name,
                type=food.type,
                city=food.city,
                phone=food.phone,
                rate=food.rate
            )
            for food in food_orm_list
        ]

        return FoodListResponse(
            city=city,
            type=type,
            count=len(foods),
            foods=foods
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"美食查询异常：{str(e)}")
        raise HTTPException(status_code=500, detail=f"美食查询失败：{str(e)}")

# === 启动入口 ===
if __name__ == "__main__":
    import uvicorn

    print(" 交互式文档: http://127.0.0.1:8000/docs")
    print(" 健康检查: http://127.0.0.1:8000/health")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)