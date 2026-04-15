from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config.config import APP_NAME, APP_VERSION, CORS_ORIGINS
from app.api import api_router
from app.services.neo4j_service import get_all_spots_from_db, driver, close_neo4j_driver
from app.services.amap_service import close_amap_session
from app.models.database import SessionLocal
from sqlalchemy import text

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
        print("✅ Neo4j + MySQL 连接成功，缓存初始化完成")
    except Exception as e:
        raise RuntimeError(f"启动失败：{e}")

    yield  # 服务运行中

    # 关闭逻辑
    close_neo4j_driver()
    # 关闭高德接口会话
    close_amap_session()
    print("🔌 数据库连接已关闭")

# === FastAPI 基础配置（绑定lifespan） ===
app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    lifespan=lifespan  # 绑定生命周期事件
)

# === CORS 跨域配置 ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api_router)

# 添加景点详情接口的重定向，兼容旧路由
from fastapi.responses import RedirectResponse
@app.get("/spot/{spot_name}")
async def redirect_spot_detail(spot_name: str):
    return RedirectResponse(url=f"/recommend/spot/{spot_name}")

# === 启动入口 ===
if __name__ == "__main__":
    import uvicorn

    print(" 交互式文档: http://127.0.0.1:8000/docs")
    print(" 健康检查: http://127.0.0.1:8000/health")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
