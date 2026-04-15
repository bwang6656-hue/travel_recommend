from sqlalchemy import Column, Integer, String, DECIMAL, Float, DateTime
from datetime import datetime
from app.models.database import Base

class DBUser(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    password = Column(String(255), nullable=False)

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
    user_id = Column(Integer,nullable=False, comment="用户ID")
    spot_id = Column(Integer, nullable=False, comment="景点ID")
    visit_time = Column(DateTime, default=datetime.now, comment="访问时间")
