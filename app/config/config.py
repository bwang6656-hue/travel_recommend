import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 数据库配置
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

SQLALCHEMY_DATABASE_URL = os.getenv(
    "MYSQL_URL",
    "mysql+pymysql://root:zxzdxc86@localhost:3306/travel"
)

# 高德API配置
AMAP_KEY = os.getenv("AMAP_KEY")
AMAP_DISTRICT_URL = os.getenv("AMAP_DISTRICT_URL", "https://restapi.amap.com/v3/config/district")
AMAP_WEATHER_URL = os.getenv("AMAP_WEATHER_URL", "https://restapi.amap.com/v3/weather/weatherInfo")

# 通义千问API配置
QWEN_API_KEY = os.getenv("QWEN_API_KEY")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-turbo")

RAG_EMBEDDING_MODEL = os.getenv("RAG_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
RAG_EMBEDDING_DIM = int(os.getenv("RAG_EMBEDDING_DIM", "512"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "30"))

# 应用配置
APP_NAME = "智能旅游景点推荐系统"
APP_VERSION = "2.5.0"

# CORS配置
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# 缓存配置
CACHE_EXPIRE = 36000  # 10小时

# 验证配置
PASSWORD_SCHEMES = ["bcrypt"]
