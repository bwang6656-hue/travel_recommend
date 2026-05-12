from sqlalchemy import Column, Integer, String, DECIMAL, Float, DateTime, Boolean, Text, Date
from datetime import datetime, date
from app.models.database import Base


class DBUser(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    password = Column(String(255), nullable=False)
    role = Column(String(50), default="user", nullable=False)
    birthday = Column(Date, nullable=True)
    gender = Column(String(10), default="保密", nullable=False)
    avatar = Column(String(500), nullable=True)


class DBHotel(Base):
    __tablename__ = "hotel"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, comment="酒店名")
    city = Column(String(255), nullable=False, comment="城市")
    price = Column(DECIMAL(10, 2), nullable=False, comment="价格")
    phone = Column(String(255), nullable=True, comment="联系方式")
    rate = Column(Float, nullable=False, comment="评分")


class DBFood(Base):
    __tablename__ = "food"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, comment="店名")
    type = Column(String(255), nullable=False, comment="食物类型")
    phone = Column(String(255), nullable=True, comment="联系电话")
    city = Column(String(255), nullable=False, comment="所处城市")
    rate = Column(Float, nullable=False, comment="评分")


class DBFootprint(Base):
    __tablename__ = "user_footprint"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, comment="用户ID")
    spot_id = Column(Integer, nullable=False, comment="景点ID")
    visit_time = Column(DateTime, default=datetime.now, comment="访问时间")


class DBFavorite(Base):
    __tablename__ = "user_favorites"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    spot_id = Column(Integer, nullable=False)
    spotname = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class DBNotification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=True)
    type = Column(String(50), default="system")
    is_read = Column(Boolean, default=False)
    read_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)


class DBFeedback(Base):
    __tablename__ = "user_feedback"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, nullable=True)
    username = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    type = Column(String(50), default="suggestion")
    create_time = Column(DateTime, default=datetime.now)


class DBChatHistory(Base):
    __tablename__ = "chat_history"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    role = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
