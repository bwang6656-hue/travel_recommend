from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

# 用户相关模型
class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, description="用户名（必填，3位以上）")
    password: str = Field(..., min_length=6, description="密码（必填，6位以上）")
    email: Optional[EmailStr] = Field(None, description="邮箱（可选，不要求唯一）")

class UserLoginRequest(BaseModel):
    username: str = Field(..., description="用户名（必填）")
    password: str = Field(..., description="密码（必填）")

class UserInfoResponse(BaseModel):
    id: int
    username: str
    email: Optional[str]

class UserUpdateRequest(BaseModel):
    email: Optional[EmailStr] = Field(None, description="邮箱（可选，不要求唯一）")
    password: Optional[str] = Field(None, min_length=6, description="新密码（可选，6位以上）")

# 足迹相关模型
class FootprintRequest(BaseModel):
    user_id: int = Field(..., ge=1, description="用户ID")
    spot_id: int = Field(..., ge=1, description="景点ID")

class FootprintResponse(BaseModel):
    id: int
    user_id: int
    spot_id: int
    visit_time: datetime
    class Config:
        from_attributes = True

class FootprintListResponse(BaseModel):
    user_id: int
    count: int
    footprints: List[FootprintResponse]

# 推荐相关模型
class RecommendationItem(BaseModel):
    spot_id: int
    name: str
    city: str
    rating: float
    reason: str
    weather: Optional[Dict[str, str]] = Field(None, description="景点所在城市实时天气")

class SpotDetail(BaseModel):
    spot_id: int
    name: str
    city: str
    rating: float
    address: str
    types: str

class CityRecommendationItem(BaseModel):
    spot_id: int
    name: str
    city: str
    rating: float

class RecommendationResponse(BaseModel):
    target: str
    count: int
    recommendations: List[RecommendationItem]

class CityRecommendationResponse(BaseModel):
    city: str
    count: int
    recommendations: List[CityRecommendationItem]

# 酒店相关模型
class HotelItem(BaseModel):
    id: int
    name: str
    city: str
    price: float
    phone: Optional[str]
    rate: float

class HotelListResponse(BaseModel):
    city: str
    count: int
    hotels: List[HotelItem]

# 美食相关模型
class FoodItem(BaseModel):
    id: int
    name: str
    type: str
    city: str
    phone: Optional[str]
    rate: float

class FoodListResponse(BaseModel):
    city: str
    type: str
    count: int
    foods: List[FoodItem]

# AI行程相关模型
class AITripRequest(BaseModel):
    spots: List[Dict[str, Any]] = Field(..., description="景点列表（含name/city/type字段）")
    days: int = Field(1, ge=1, le=3, description="行程天数（1-3天）")
    preference: Optional[str] = Field(None, description="游玩偏好（如美食优先、休闲放松）")

class AITripResponse(BaseModel):
    itinerary: str = Field(..., description="自然语言行程文案")
    days: int = Field(..., description="行程天数")
    preference: Optional[str] = Field(None, description="游玩偏好")

# 通用响应模型
class DeleteSuccessResponse(BaseModel):
    status: str
    detail: str
