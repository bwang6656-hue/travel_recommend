from fastapi import APIRouter, HTTPException
from app.services.neo4j_service import driver
from app.models.database import SessionLocal
from sqlalchemy import text

router = APIRouter(tags=["健康检查"])

# 健康检查
@router.get("/health")
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
