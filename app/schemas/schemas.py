from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, description="用户名（必填，3位以上）")
    password: str = Field(..., min_length=6, description="密码（必填，6位以上）")
    email: Optional[EmailStr] = Field(None, description="邮箱（可选，不要求唯一）")
    role: Optional[str] = Field("user", description="角色：user/admin")

class UserLoginRequest(BaseModel):
    username: str = Field(..., description="用户名（必填）")
    password: str = Field(..., description="密码（必填）")
    role: Optional[str] = Field("user", description="角色：user/admin")

class UserInfoResponse(BaseModel):
    id: int
    username: str
    email: Optional[str]
    role: Optional[str] = "user"

class UserUpdateRequest(BaseModel):
    email: Optional[EmailStr] = Field(None, description="邮箱（可选，不要求唯一）")
    password: Optional[str] = Field(None, min_length=6, description="新密码（可选，6位以上）")


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


class FavoriteRequest(BaseModel):
    user_id: int = Field(..., ge=1, description="用户ID")
    spot_id: int = Field(..., ge=1, description="景点ID")

class FavoriteItem(BaseModel):
    id: int
    user_id: int
    spot_id: int
    created_at: datetime
    class Config:
        from_attributes = True

class FavoriteListResponse(BaseModel):
    user_id: int
    count: int
    favorites: List[FavoriteItem]


class NotificationItem(BaseModel):
    id: int
    user_id: int
    title: str
    content: Optional[str]
    type: str
    is_read: bool
    created_at: datetime
    class Config:
        from_attributes = True

class NotificationListResponse(BaseModel):
    count: int
    notifications: List[NotificationItem]


class FeedbackRequest(BaseModel):
    user_id: Optional[int] = Field(None, description="用户ID（可选）")
    content: str = Field(..., min_length=5, description="反馈内容")
    contact: Optional[str] = Field(None, description="联系方式")

class FeedbackResponse(BaseModel):
    id: int
    user_id: Optional[int]
    content: str
    contact: Optional[str]
    created_at: datetime
    class Config:
        from_attributes = True


class ChatMessageRequest(BaseModel):
    user_id: int = Field(..., ge=1, description="用户ID")
    message: str = Field(..., min_length=1, description="消息内容")

class ChatMessageItem(BaseModel):
    id: int
    user_id: int
    role: str
    content: str
    created_at: datetime
    class Config:
        from_attributes = True

class ChatMessageResponse(BaseModel):
    reply: str = Field(..., description="客服回复")
    history: List[ChatMessageItem] = Field(default_factory=list, description="聊天记录")

class ChatHistoryResponse(BaseModel):
    user_id: int
    count: int
    messages: List[ChatMessageItem]


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


class AITripRequest(BaseModel):
    spots: List[Dict[str, Any]] = Field(..., description="景点列表（含name/city/type字段）")
    days: int = Field(1, ge=1, le=3, description="行程天数（1-3天）")
    preference: Optional[str] = Field(None, description="游玩偏好（如美食优先、休闲放松）")

class AITripResponse(BaseModel):
    itinerary: str = Field(..., description="自然语言行程文案")
    days: int = Field(..., description="行程天数")
    preference: Optional[str] = Field(None, description="游玩偏好")

class NaturalLanguageTripRequest(BaseModel):
    query: str = Field(..., min_length=2, description="自然语言行程需求，如'我想去北京玩3天，喜欢历史文化'")

class RelatedSpotItem(BaseModel):
    spot_id: int
    name: str
    city: str
    rating: float
    price: Optional[float] = None
    best_season: Optional[str] = None
    recommended_duration: Optional[str] = None
    tags: Optional[List[str]] = None

class ChatHistoryItem(BaseModel):
    role: str = Field(..., description="消息角色：user/assistant")
    content: str = Field(..., description="消息内容")

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户消息")
    history: List[ChatHistoryItem] = Field(default_factory=list, description="对话历史")
    system_prompt: str = Field("", description="自定义系统提示词")

class ChatReplyResponse(BaseModel):
    reply: str = Field(..., description="AI回复")
    related_spots: List[RelatedSpotItem] = Field(default_factory=list, description="相关景点")
    city: Optional[str] = Field(None, description="识别出的城市")
    preference: Optional[str] = Field(None, description="识别出的偏好")

class NaturalLanguageTripResponse(BaseModel):
    query: str = Field(..., description="用户原始查询")
    itinerary: str = Field(..., description="AI生成的行程方案")
    related_spots: List[RelatedSpotItem] = Field(default_factory=list, description="检索到的相关景点")
    days: int = Field(..., description="行程天数")
    city: Optional[str] = Field(None, description="识别出的城市")
    preference: Optional[str] = Field(None, description="识别出的偏好")


class AdminDashboardStats(BaseModel):
    total_users: int
    total_spots: int
    total_footprints: int
    total_favorites: int
    active_users_today: int

class AdminTrendItem(BaseModel):
    date: str
    users: int
    footprints: int
    favorites: int

class AdminTrendResponse(BaseModel):
    trends: List[AdminTrendItem]

class AdminUserItem(BaseModel):
    id: int
    username: str
    email: Optional[str]
    role: str
    status: str

class AdminUserListResponse(BaseModel):
    count: int
    users: List[AdminUserItem]

class AdminRoleUpdateRequest(BaseModel):
    role: str = Field(..., description="新角色：user/admin")

class AdminStatusUpdateRequest(BaseModel):
    status: str = Field(..., description="新状态：active/disabled")


class DeleteSuccessResponse(BaseModel):
    status: str
    detail: str
