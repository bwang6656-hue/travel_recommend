from fastapi import APIRouter, HTTPException, Depends, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from datetime import datetime, timedelta
from app.models.database import get_db
from app.models.models import DBUser, DBFootprint, DBFavorite
from app.schemas.schemas import (
    AdminDashboardStats, AdminTrendItem, AdminTrendResponse,
    AdminUserItem, AdminUserListResponse, AdminRoleUpdateRequest,
    AdminStatusUpdateRequest,
)

router = APIRouter(prefix="/admin", tags=["管理后台"])


@router.get("/dashboard/stats", response_model=AdminDashboardStats, summary="仪表盘统计")
def get_dashboard_stats(db: Session = Depends(get_db)):
    try:
        total_users = db.query(DBUser).count()
        total_spots = db.execute(text("SELECT COUNT(*) FROM user_footprint")).scalar() or 0
        total_footprints = db.query(DBFootprint).count()
        total_favorites = db.query(DBFavorite).count()

        today = datetime.now().date()
        active_users_today = db.query(DBFootprint).filter(
            func.date(DBFootprint.visit_time) == today
        ).count()

        return AdminDashboardStats(
            total_users=total_users,
            total_spots=total_spots,
            total_footprints=total_footprints,
            total_favorites=total_favorites,
            active_users_today=active_users_today,
        )
    except Exception as e:
        print(f"仪表盘统计失败：{str(e)}")
        raise HTTPException(status_code=500, detail=f"统计失败：{str(e)}")


@router.get("/dashboard/trends", response_model=AdminTrendResponse, summary="趋势数据")
def get_dashboard_trends(
        days: int = Query(7, ge=1, le=30, description="统计天数"),
        db: Session = Depends(get_db)
):
    try:
        trends = []
        for i in range(days - 1, -1, -1):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            footprints_count = db.query(DBFootprint).filter(
                func.date(DBFootprint.visit_time) == date
            ).count()
            favorites_count = db.query(DBFavorite).filter(
                func.date(DBFavorite.created_at) == date
            ).count()
            trends.append(AdminTrendItem(
                date=date,
                users=0,
                footprints=footprints_count,
                favorites=favorites_count,
            ))
        return AdminTrendResponse(trends=trends)
    except Exception as e:
        print(f"趋势数据获取失败：{str(e)}")
        raise HTTPException(status_code=500, detail=f"趋势数据获取失败：{str(e)}")


@router.get("/users", response_model=AdminUserListResponse, summary="用户列表")
def get_user_list(
        role: str = Query(None, description="按角色筛选：user/admin"),
        status: str = Query(None, description="按状态筛选：active/disabled"),
        db: Session = Depends(get_db)
):
    try:
        query = db.query(DBUser)
        if role:
            query = query.filter(DBUser.role == role)
        if status:
            query = query.filter(DBUser.status == status)
        users = query.order_by(DBUser.id).all()
        items = [
            AdminUserItem(
                id=u.id,
                username=u.username,
                email=u.email,
                role=u.role or "user",
                status=u.status or "active",
            )
            for u in users
        ]
        return AdminUserListResponse(count=len(items), users=items)
    except Exception as e:
        print(f"获取用户列表失败：{str(e)}")
        raise HTTPException(status_code=500, detail=f"获取用户列表失败：{str(e)}")


@router.put("/users/{user_id}/role", summary="修改用户角色")
def update_user_role(
        user_id: int,
        req: AdminRoleUpdateRequest = Body(...),
        db: Session = Depends(get_db)
):
    try:
        user = db.query(DBUser).filter(DBUser.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        if req.role not in ("user", "admin"):
            raise HTTPException(status_code=400, detail="角色只能为 user 或 admin")
        user.role = req.role
        db.commit()
        return {"status": "ok", "detail": f"用户 {user.username} 角色已修改为 {req.role}"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"修改角色失败：{str(e)}")


@router.put("/users/{user_id}/status", summary="修改用户状态")
def update_user_status(
        user_id: int,
        req: AdminStatusUpdateRequest = Body(...),
        db: Session = Depends(get_db)
):
    try:
        user = db.query(DBUser).filter(DBUser.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        if req.status not in ("active", "disabled"):
            raise HTTPException(status_code=400, detail="状态只能为 active 或 disabled")
        user.status = req.status
        db.commit()
        return {"status": "ok", "detail": f"用户 {user.username} 状态已修改为 {req.status}"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"修改状态失败：{str(e)}")
