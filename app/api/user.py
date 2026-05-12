from fastapi import APIRouter, HTTPException, Depends, Query, Body
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.models.models import DBUser, DBFootprint, DBFavorite, DBNotification
from app.schemas.schemas import (
    UserInfoResponse, UserUpdateRequest, FootprintRequest, FootprintResponse,
    FootprintListResponse, DeleteSuccessResponse, FavoriteRequest, FavoriteItem,
    FavoriteListResponse, NotificationItem, NotificationListResponse,
    AnnouncementItem, AnnouncementListResponse,
    UserNotificationItem, UserNotificationListResponse,
)
from app.services.auth_service import get_password_hash
from app.services.neo4j_service import get_all_spots_from_db, clear_footprint_cache
from datetime import datetime

router = APIRouter(prefix="/user", tags=["用户"])


@router.post("/footprints", response_model=FootprintResponse)
def add_user_footprint(
        footprint_data: FootprintRequest = Body(..., description="用户足迹"),
        db: Session = Depends(get_db)
):
    try:
        user_exists = db.query(DBUser).filter(DBUser.id == footprint_data.user_id).first()
        if not user_exists:
            raise HTTPException(status_code=404, detail=f"用户ID {footprint_data.user_id} 不存在")
        all_spots = get_all_spots_from_db()
        if footprint_data.spot_id not in all_spots:
            raise HTTPException(status_code=404, detail=f"景点ID {footprint_data.spot_id} 不存在")

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

        clear_footprint_cache()
        return new_footprint
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"添加足迹失败：{str(e)}")
        raise HTTPException(status_code=500, detail=f"添加足迹失败:{str(e)}")


@router.get("/footprints", response_model=FootprintListResponse)
def get_user_footprints(
        user_id: int = Query(..., ge=1, description="用户ID "),
        db: Session = Depends(get_db)
):
    try:
        footprints_orm = db.query(DBFootprint).filter(DBFootprint.user_id == user_id).order_by(
            DBFootprint.visit_time.desc()).all()
        footprints = [FootprintResponse.model_validate(fp) for fp in footprints_orm]
        return FootprintListResponse(
            user_id=user_id,
            count=len(footprints),
            footprints=footprints
        )
    except Exception as e:
        print(f"获取足迹失败{str(e)}")
        raise HTTPException(status_code=500, detail=f"获取足迹失败{str(e)}")


@router.delete("/footprints", response_model=DeleteSuccessResponse)
def delete_user_footprints(
        footprint_data: FootprintRequest = Body(..., description="用户足迹"),
        db: Session = Depends(get_db)
):
    try:
        user_exist = db.query(DBUser).filter(DBUser.id == footprint_data.user_id).first()
        if not user_exist:
            raise HTTPException(status_code=404, detail=f"用户ID {footprint_data.user_id} 不存在")

        exist_footprint = db.query(DBFootprint).filter(
            DBFootprint.user_id == footprint_data.user_id,
            DBFootprint.spot_id == footprint_data.spot_id
        ).first()
        if not exist_footprint:
            raise HTTPException(status_code=404, detail=f"该足迹不存在")
        db.delete(exist_footprint)
        db.commit()

        clear_footprint_cache()
        return {"status": "ok", "detail": "足迹删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"足迹删除失败{str(e)}")
        raise HTTPException(status_code=500, detail=f"用户足迹删除失败{str(e)}")


@router.post("/favorites", response_model=FavoriteItem, summary="添加收藏")
def add_favorite(
        req: FavoriteRequest = Body(...),
        db: Session = Depends(get_db)
):
    try:
        user = db.query(DBUser).filter(DBUser.id == req.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        all_spots = get_all_spots_from_db()
        if req.spot_id not in all_spots:
            raise HTTPException(status_code=404, detail="景点不存在")

        existing = db.query(DBFavorite).filter(
            DBFavorite.user_id == req.user_id,
            DBFavorite.spot_id == req.spot_id,
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="已收藏该景点")

        fav = DBFavorite(
            user_id=req.user_id,
            username=user.username,
            spot_id=req.spot_id,
            spotname=all_spots[req.spot_id].get("name", ""),
        )
        db.add(fav)
        db.commit()
        db.refresh(fav)
        return FavoriteItem.model_validate(fav)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"收藏失败：{str(e)}")


@router.get("/favorites", response_model=FavoriteListResponse, summary="获取收藏列表")
def get_favorites(
        user_id: int = Query(..., ge=1, description="用户ID"),
        db: Session = Depends(get_db)
):
    try:
        favs = db.query(DBFavorite).filter(
            DBFavorite.user_id == user_id
        ).order_by(DBFavorite.created_at.desc()).all()
        items = [FavoriteItem.model_validate(f) for f in favs]
        return FavoriteListResponse(user_id=user_id, count=len(items), favorites=items)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取收藏失败：{str(e)}")


@router.delete("/favorites", response_model=DeleteSuccessResponse, summary="取消收藏")
def delete_favorite(
        req: FavoriteRequest = Body(...),
        db: Session = Depends(get_db)
):
    try:
        existing = db.query(DBFavorite).filter(
            DBFavorite.user_id == req.user_id,
            DBFavorite.spot_id == req.spot_id,
        ).first()
        if not existing:
            raise HTTPException(status_code=404, detail="未收藏该景点")
        db.delete(existing)
        db.commit()
        return {"status": "ok", "detail": "取消收藏成功"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"取消收藏失败：{str(e)}")


@router.get("/notifications", response_model=UserNotificationListResponse, summary="获取用户通知列表")
def get_user_notifications(
        user_id: int = Query(..., description="用户ID"),
        db: Session = Depends(get_db)
):
    try:
        announcements = db.query(DBNotification).filter(
            DBNotification.user_id == 0,
            DBNotification.type.in_(["系统通知", "活动公告", "维护通知", "版本更新"])
        ).order_by(DBNotification.created_at.desc()).all()

        items = []
        for ann in announcements:
            read_record = db.query(DBNotification).filter(
                DBNotification.user_id == user_id,
                DBNotification.title == ann.title,
                DBNotification.content == ann.content,
                DBNotification.is_read == True
            ).first()
            items.append(UserNotificationItem(
                id=ann.id,
                title=ann.title,
                content=ann.content,
                type=ann.type,
                is_read=read_record is not None,
                created_at=ann.created_at
            ))
        return UserNotificationListResponse(count=len(items), notifications=items)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取通知列表失败：{str(e)}")


@router.put("/notifications/{announcement_id}/read", summary="标记单条已读")
def mark_notification_read(
        announcement_id: int,
        user_id: int = Query(..., description="用户ID"),
        db: Session = Depends(get_db)
):
    try:
        ann = db.query(DBNotification).filter(
            DBNotification.id == announcement_id,
            DBNotification.user_id == 0
        ).first()
        if not ann:
            raise HTTPException(status_code=404, detail="公告不存在")

        existing = db.query(DBNotification).filter(
            DBNotification.user_id == user_id,
            DBNotification.title == ann.title,
            DBNotification.content == ann.content,
            DBNotification.is_read == True
        ).first()
        if not existing:
            read_record = DBNotification(
                user_id=user_id,
                title=ann.title,
                content=ann.content,
                type=ann.type,
                is_read=True,
                read_count=0,
            )
            db.add(read_record)
            ann.read_count = (ann.read_count or 0) + 1
            db.commit()
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"标记已读失败：{str(e)}")


@router.put("/notifications/read-all", summary="全部标记已读")
def mark_all_notifications_read(
        user_id: int = Query(..., description="用户ID"),
        db: Session = Depends(get_db)
):
    try:
        announcements = db.query(DBNotification).filter(
            DBNotification.user_id == 0,
            DBNotification.type.in_(["系统通知", "活动公告", "维护通知", "版本更新"])
        ).all()

        for ann in announcements:
            existing = db.query(DBNotification).filter(
                DBNotification.user_id == user_id,
                DBNotification.title == ann.title,
                DBNotification.content == ann.content,
                DBNotification.is_read == True
            ).first()
            if not existing:
                read_record = DBNotification(
                    user_id=user_id,
                    title=ann.title,
                    content=ann.content,
                    type=ann.type,
                    is_read=True,
                    read_count=0,
                )
                db.add(read_record)
                ann.read_count = (ann.read_count or 0) + 1
        db.commit()
        return {"status": "ok"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"标记全部已读失败：{str(e)}")


@router.get("/announcements", response_model=AnnouncementListResponse, summary="查询公告列表")
def get_announcements(db: Session = Depends(get_db)):
    try:
        announcements = db.query(DBNotification).filter(
            DBNotification.user_id == 0,
        ).filter(
            DBNotification.type.in_(["系统通知", "活动公告", "维护通知", "版本更新"])
        ).order_by(DBNotification.created_at.desc()).all()
        items = [AnnouncementItem.model_validate(a) for a in announcements]
        return AnnouncementListResponse(count=len(items), announcements=items)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询公告失败：{str(e)}")


@router.put("/announcements/{announcement_id}/read", summary="标记公告已读")
def mark_announcement_read(
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
        announcement.read_count = (announcement.read_count or 0) + 1
        db.commit()
        return {"status": "ok", "detail": "已标记为已读", "read_count": announcement.read_count}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"标记已读失败：{str(e)}")


@router.get("/{user_id}", response_model=UserInfoResponse, summary="获取用户信息")
def get_user_info(
        user_id: int,
        db: Session = Depends(get_db)
):
    try:
        user = db.query(DBUser).filter(DBUser.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        return UserInfoResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            birthday=user.birthday,
            gender=user.gender,
            avatar=user.avatar,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取用户信息失败：{str(e)}")


@router.put("/{user_id}", response_model=UserInfoResponse, summary="修改用户信息")
def update_user_info(
        user_id: int,
        update_data: UserUpdateRequest = Body(...),
        db: Session = Depends(get_db)
):
    try:
        user = db.query(DBUser).filter(DBUser.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        if update_data.email is not None:
            user.email = update_data.email
        if update_data.password is not None:
            user.password = get_password_hash(update_data.password)
        if update_data.birthday is not None:
            user.birthday = update_data.birthday
        if update_data.gender is not None:
            if update_data.gender not in ("男", "女", "保密"):
                raise HTTPException(status_code=400, detail="性别只能是'男'、'女'或'保密'")
            user.gender = update_data.gender
        if update_data.avatar is not None:
            user.avatar = update_data.avatar
        db.commit()
        db.refresh(user)
        return UserInfoResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            birthday=user.birthday,
            gender=user.gender,
            avatar=user.avatar,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"修改用户信息失败：{str(e)}")
