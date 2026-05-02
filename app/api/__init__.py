from fastapi import APIRouter
from app.api import auth, user, recommend, hotel_food, health, chat, feedback, admin

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(user.router)
api_router.include_router(recommend.router)
api_router.include_router(hotel_food.router)
api_router.include_router(health.router)
api_router.include_router(chat.router)
api_router.include_router(feedback.router)
api_router.include_router(admin.router)
