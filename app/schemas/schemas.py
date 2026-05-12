from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, date


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
    birthday: Optional[date] = None
    gender: Optional[str] = "保密"
    avatar: Optional[str] = None

class UserUpdateRequest(BaseModel):
    email: Optional[EmailStr] = Field(None, description="邮箱")
    password: Optional[str] = Field(None, min_length=6, description="新密码")
    birthday: Optional[date] = Field(None, description="生日")
    gender: Optional[str] = Field(None, description="性别：男/女/保密")
    avatar: Optional[str] = Field(None, description="头像URL")


class FootprintRequest(BaseModel):
    user_id: int = Field(..., ge=1, description="用户ID")
    spot_id: int = Field(..., ge=1, description="景点ID")

class FootprintResponse(BaseModel):
    id: int
    user_id: int
    spot_id: int
    visit_time: datetime
    class Config:
        #from_attributes = True 允许从ORM对象创建模型实例
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
    username: Optional[str] = None
    spot_id: int
    spotname: Optional[str] = None
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
    username: Optional[str] = Field(None, description="用户名")
    content: str = Field(..., min_length=2, description="反馈内容")
    type: Optional[str] = Field("suggestion", description="反馈类型：suggestion/complaint/bug/other")

class FeedbackResponse(BaseModel):
    id: int
    user_id: Optional[int]
    username: Optional[str]
    content: str
    type: str
    create_time: datetime
    class Config:
        from_attributes = True

class FeedbackListResponse(BaseModel):
    count: int
    feedbacks: List[FeedbackResponse]


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
    weather: Optional[Dict[str, str]] = Field(None, description="景点所在城市实时天气")

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

class HotelCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, description="酒店名")
    city: str = Field(..., min_length=1, description="城市")
    price: float = Field(..., gt=0, description="价格")
    phone: Optional[str] = Field(None, description="联系方式")
    rate: float = Field(..., ge=0, le=5, description="评分(0-5)")

class HotelUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, description="酒店名")
    city: Optional[str] = Field(None, min_length=1, description="城市")
    price: Optional[float] = Field(None, gt=0, description="价格")
    phone: Optional[str] = Field(None, description="联系方式")
    rate: Optional[float] = Field(None, ge=0, le=5, description="评分(0-5)")

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

class FoodCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, description="店名")
    type: str = Field(..., min_length=1, description="食物类型")
    city: str = Field(..., min_length=1, description="城市")
    phone: Optional[str] = Field(None, description="联系电话")
    rate: float = Field(..., ge=0, le=5, description="评分(0-5)")

class FoodUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, description="店名")
    type: Optional[str] = Field(None, min_length=1, description="食物类型")
    city: Optional[str] = Field(None, min_length=1, description="城市")
    phone: Optional[str] = Field(None, description="联系电话")
    rate: Optional[float] = Field(None, ge=0, le=5, description="评分(0-5)")

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
    birthday: Optional[date] = None
    gender: Optional[str] = "保密"
    avatar: Optional[str] = None

class AdminUserListResponse(BaseModel):
    count: int
    users: List[AdminUserItem]

class AdminRoleUpdateRequest(BaseModel):
    role: str = Field(..., description="新角色：user/admin")


class SpotListItem(BaseModel):
    spot_id: int
    name: str
    city: str
    rating: float
    address: str
    types: str

class SpotListResponse(BaseModel):
    count: int
    spots: List[SpotListItem]


class UserNotificationItem(BaseModel):
    id: int
    title: str
    content: Optional[str]
    type: str
    is_read: bool
    created_at: datetime

class UserNotificationListResponse(BaseModel):
    count: int
    notifications: List[UserNotificationItem]


class AnnouncementCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, description="公告标题")
    content: str = Field(..., min_length=1, description="公告内容")
    type: Optional[str] = Field("系统通知", description="公告类型：系统通知/活动公告/维护通知/版本更新")

class AnnouncementItem(BaseModel):
    id: int
    title: str
    content: Optional[str]
    type: str
    read_count: int
    created_at: datetime
    class Config:
        from_attributes = True

class AnnouncementListResponse(BaseModel):
    count: int
    announcements: List[AnnouncementItem]


class DeleteSuccessResponse(BaseModel):
    status: str
    detail: str
