from fastapi import APIRouter, HTTPException, Depends, Query, Body
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.models.models import DBUser, DBFootprint
from app.schemas.schemas import UserInfoResponse, UserUpdateRequest, FootprintRequest, FootprintResponse, FootprintListResponse, DeleteSuccessResponse
from app.services.auth_service import get_password_hash
from app.services.neo4j_service import get_all_spots_from_db, clear_footprint_cache
from datetime import datetime

router = APIRouter(prefix="/user", tags=["用户"])

# 获取用户信息
@router.get("/{user_id}", response_model=UserInfoResponse, summary="获取用户信息")
def get_user_info(
        user_id: int,  # Path(..., ge=1, description="用户ID（users表的id）"),
        db: Session = Depends(get_db)
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
@router.put("/{user_id}", response_model=UserInfoResponse, summary="修改用户信息")
def update_user_info(
        user_id: int,  # Path(..., ge=1, description="用户ID（users表的id）"),
        update_data: UserUpdateRequest = Body(...),
        db: Session = Depends(get_db)
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

# 添加用户足迹
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

        # 清除缓存
        clear_footprint_cache()
        return new_footprint
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"添加足迹失败：{str(e)}")
        raise HTTPException(status_code=500, detail=f"添加足迹失败:{str(e)}")

# 获取用户足迹
@router.get("/footprints", response_model=FootprintListResponse)
def get_user_footprints(
        user_id: int = Query(..., ge=1, description="用户ID "),
        db: Session = Depends(get_db)
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
@router.delete("/footprints", response_model=DeleteSuccessResponse)
def delete_user_footprints(
        footprint_data: FootprintRequest = Body(..., description="用户足迹"),
        db: Session = Depends(get_db)
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

        # 清除缓存
        clear_footprint_cache()
        return {"status": "ok", "detail": "足迹删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"足迹删除失败{str(e)}")
        raise HTTPException(status_code=500, detail=f"用户足迹删除失败{str(e)}")
