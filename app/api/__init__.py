from fastapi import APIRouter
from app.api import auth, user, recommend, hotel_food, health

# 创建主路由
api_router = APIRouter()

# 注册子路由
api_router.include_router(auth.router)
api_router.include_router(user.router)
api_router.include_router(recommend.router)
api_router.include_router(hotel_food.router)
api_router.include_router(health.router)
