from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.models.models import DBUser
from app.schemas.schemas import UserRegisterRequest, UserLoginRequest, UserInfoResponse
from app.services.auth_service import verify_password, get_password_hash

router = APIRouter(prefix="/auth", tags=["认证"])

@router.post("/register", response_model=UserInfoResponse, summary="用户注册")
def user_register(
        user_data: UserRegisterRequest,
        db: Session = Depends(get_db)
):
    try:
        existing_user = db.query(DBUser).filter(DBUser.username == user_data.username).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="用户名已被注册")

        role = user_data.role if user_data.role in ("user", "admin") else "user"

        hashed_password = get_password_hash(user_data.password)
        new_user = DBUser(
            username=user_data.username,
            password=hashed_password,
            email=user_data.email,
            role=role,
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return UserInfoResponse(
            id=new_user.id,
            username=new_user.username,
            email=new_user.email,
            role=new_user.role,
            birthday=new_user.birthday,
            gender=new_user.gender,
            avatar=new_user.avatar,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"注册接口报错：{str(e)}")
        raise HTTPException(status_code=500, detail=f"注册失败：{str(e)}")

@router.post("/login", response_model=UserInfoResponse, summary="用户登录")
def user_login(
        login_data: UserLoginRequest,
        db: Session = Depends(get_db)
):
    try:
        user = db.query(DBUser).filter(DBUser.username == login_data.username).first()

        if not user:
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        if not verify_password(login_data.password, user.password):
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        if login_data.role and login_data.role != user.role:
            raise HTTPException(status_code=403, detail=f"该账号不是{login_data.role}身份")

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
        print(f"登录接口报错：{str(e)}")
        raise HTTPException(status_code=500, detail=f"登录失败：{str(e)}")
