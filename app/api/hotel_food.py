from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.models.models import DBHotel, DBFood
from app.schemas.schemas import HotelListResponse, HotelItem, FoodListResponse, FoodItem

router = APIRouter(tags=["酒店和美食"])

# 酒店查询
@router.get("/hotel", response_model=HotelListResponse, summary="酒店查询")
def get_hotel_list(
        city: str = Query(..., description="城市名称，例如 '北京'、'上海'"),
        sort_by: str = Query("price", description="排序字段，可选 price（价格）、rating（评分）"),
        sort_order: str = Query("asc", description="排序方向，可选 asc（升序）、desc（降序）"),
        db: Session = Depends(get_db)
):
    try:
        sort_field = DBHotel.price if sort_by == "price" else DBHotel.rate
        if sort_order == "desc":
            sort_field = sort_field.desc()

        hotel_orm_list = db.query(DBHotel).filter(DBHotel.city == city).order_by(sort_field).all()
        if not hotel_orm_list:
            raise HTTPException(status_code=404, detail=f"城市「{city}」暂无酒店数据")

        hotels = [
            HotelItem(
                id=hotel.id,
                name=hotel.name,
                city=hotel.city,
                price=float(hotel.price),
                phone=hotel.phone,
                rate=hotel.rate
            )
            for hotel in hotel_orm_list
        ]

        return HotelListResponse(
            city=city,
            count=len(hotels),
            hotels=hotels
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"酒店查询异常：{str(e)}")
        raise HTTPException(status_code=500, detail=f"酒店查询失败：{str(e)}")

# 美食查询
@router.get("/food", response_model=FoodListResponse, summary="按城市+类型查询美食（支持排序）")
def get_food_list(
        city: str = Query(..., description="城市名称，例如 '北京'、'上海'"),
        type: str = Query(..., description="食物类型，可选 地方菜系、火锅烧烤、小吃快餐"),
        sort_order: str = Query("desc", description="排序方向，可选 asc（升序）、desc（降序）"),
        db: Session = Depends(get_db)
):
    try:
        sort_field = DBFood.rate.desc() if sort_order == "desc" else DBFood.rate.asc()

        food_orm_list = db.query(DBFood).filter(DBFood.city == city, DBFood.type == type).order_by(sort_field).all()
        if not food_orm_list:
            raise HTTPException(status_code=404, detail=f"城市「{city}」暂无类型为「{type}」的美食数据")

        foods = [
            FoodItem(
                id=food.id,
                name=food.name,
                type=food.type,
                city=food.city,
                phone=food.phone,
                rate=food.rate
            )
            for food in food_orm_list
        ]

        return FoodListResponse(
            city=city,
            type=type,
            count=len(foods),
            foods=foods
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"美食查询异常：{str(e)}")
        raise HTTPException(status_code=500, detail=f"美食查询失败：{str(e)}")
