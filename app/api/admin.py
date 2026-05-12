from fastapi import APIRouter, HTTPException, Depends, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from datetime import datetime, timedelta
from app.models.database import get_db
from app.models.models import DBUser, DBFootprint, DBFavorite, DBFeedback, DBNotification
from app.schemas.schemas import (
    AdminDashboardStats, AdminTrendItem, AdminTrendResponse,
    AdminUserItem, AdminUserListResponse, AdminRoleUpdateRequest,
    FeedbackListResponse, FeedbackResponse,
    AnnouncementCreateRequest, AnnouncementItem, AnnouncementListResponse,
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
        db: Session = Depends(get_db)
):
    try:
        query = db.query(DBUser)
        if role:
            query = query.filter(DBUser.role == role)
        users = query.order_by(DBUser.id).all()
        items = [
            AdminUserItem(
                id=u.id,
                username=u.username,
                email=u.email,
                role=u.role or "user",
                birthday=u.birthday,
                gender=u.gender,
                avatar=u.avatar,
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


@router.get("/feedbacks", response_model=FeedbackListResponse, summary="获取反馈列表")
def get_feedback_list(
        type: str = Query(None, description="按类型筛选：suggestion/complaint/bug/other"),
        db: Session = Depends(get_db)
):
    try:
        query = db.query(DBFeedback)
        if type:
            query = query.filter(DBFeedback.type == type)
        feedbacks = query.order_by(DBFeedback.create_time.desc()).all()
        items = [FeedbackResponse.model_validate(f) for f in feedbacks]
        return FeedbackListResponse(count=len(items), feedbacks=items)
    except Exception as e:
        print(f"获取反馈列表失败：{str(e)}")
        raise HTTPException(status_code=500, detail=f"获取反馈列表失败：{str(e)}")


@router.post("/announcements", response_model=AnnouncementItem, summary="发布公告")
def create_announcement(
        req: AnnouncementCreateRequest = Body(...),
        db: Session = Depends(get_db)
):
    try:
        valid_types = ("系统通知", "活动公告", "维护通知", "版本更新")
        ann_type = req.type if req.type in valid_types else "系统通知"

        announcement = DBNotification(
            user_id=0,
            title=req.title,
            content=req.content,
            type=ann_type,
            is_read=False,
            read_count=0,
        )
        db.add(announcement)
        db.commit()
        db.refresh(announcement)
        return AnnouncementItem.model_validate(announcement)
    except Exception as e:
        db.rollback()
        print(f"发布公告失败：{str(e)}")
        raise HTTPException(status_code=500, detail=f"发布公告失败：{str(e)}")


@router.get("/announcements", response_model=AnnouncementListResponse, summary="查询公告列表")
def get_announcement_list(db: Session = Depends(get_db)):
    try:
        announcements = db.query(DBNotification).filter(
            DBNotification.user_id == 0,
        ).filter(
            DBNotification.type.in_(["系统通知", "活动公告", "维护通知", "版本更新"])
        ).order_by(DBNotification.created_at.desc()).all()
        items = [AnnouncementItem.model_validate(a) for a in announcements]
        return AnnouncementListResponse(count=len(items), announcements=items)
    except Exception as e:
        print(f"查询公告失败：{str(e)}")
        raise HTTPException(status_code=500, detail=f"查询公告失败：{str(e)}")


@router.delete("/announcements/{announcement_id}", summary="删除公告")
def delete_announcement(
        announcement_id: int,
        db: Session = Depends(get_db)
):
    try:
        announcement = db.query(DBNotification).filter(
            DBNotification.id == announcement_id,
            DBNotification.user_id == 0,
        ).first()
        if not announcement:
            raise HTTPException(status_code=404, detail="公告不存在")
        db.delete(announcement)
        db.commit()
        return {"status": "ok", "detail": "公告删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"删除公告失败：{str(e)}")
        raise HTTPException(status_code=500, detail=f"删除公告失败：{str(e)}")
