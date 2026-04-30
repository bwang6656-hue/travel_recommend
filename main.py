from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config.config import APP_NAME, APP_VERSION, CORS_ORIGINS
from app.api import api_router
from app.services.neo4j_service import get_all_spots_from_db, driver, close_neo4j_driver
from app.services.amap_service import close_amap_session
from app.services.vector_store_service import vector_store_service
from app.models.database import SessionLocal
from sqlalchemy import text

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        driver.verify_connectivity()
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        get_all_spots_from_db()
        print("[OK] Neo4j + MySQL 连接成功，缓存初始化完成")
    except Exception as e:
        raise RuntimeError(f"启动失败：{e}")

    try:
        print("[RAG] 初始化向量存储服务...")
        vector_store_service.build_index()
        print("[OK] RAG向量索引初始化完成")
    except Exception as e:
        print(f"[WARN] RAG初始化失败（自然语言行程功能不可用）：{e}")

    yield

    close_neo4j_driver()
    close_amap_session()
    print("[OK] 数据库连接已关闭")

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
