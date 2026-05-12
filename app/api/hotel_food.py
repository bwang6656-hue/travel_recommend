from fastapi import APIRouter, HTTPException, Depends, Query, Body
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.models.models import DBHotel, DBFood
from app.schemas.schemas import (
    HotelListResponse, HotelItem, HotelCreateRequest, HotelUpdateRequest,
    FoodListResponse, FoodItem, FoodCreateRequest, FoodUpdateRequest,
)

router = APIRouter(tags=["酒店和美食"])


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


@router.post("/hotel", response_model=HotelItem, summary="新增酒店")
def create_hotel(
        req: HotelCreateRequest = Body(...),
        db: Session = Depends(get_db)
):
    try:
        hotel = DBHotel(
            name=req.name,
            city=req.city,
            price=req.price,
            phone=req.phone,
            rate=req.rate,
        )
        db.add(hotel)
        db.commit()
        db.refresh(hotel)
        return HotelItem(
            id=hotel.id,
            name=hotel.name,
            city=hotel.city,
            price=float(hotel.price),
            phone=hotel.phone,
            rate=hotel.rate,
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"新增酒店失败：{str(e)}")


@router.put("/hotel/{hotel_id}", response_model=HotelItem, summary="修改酒店信息")
def update_hotel(
        hotel_id: int,
        req: HotelUpdateRequest = Body(...),
        db: Session = Depends(get_db)
):
    try:
        hotel = db.query(DBHotel).filter(DBHotel.id == hotel_id).first()
        if not hotel:
            raise HTTPException(status_code=404, detail="酒店不存在")
        if req.name is not None:
            hotel.name = req.name
        if req.city is not None:
            hotel.city = req.city
        if req.price is not None:
            hotel.price = req.price
        if req.phone is not None:
            hotel.phone = req.phone
        if req.rate is not None:
            hotel.rate = req.rate
        db.commit()
        db.refresh(hotel)
        return HotelItem(
            id=hotel.id,
            name=hotel.name,
            city=hotel.city,
            price=float(hotel.price),
            phone=hotel.phone,
            rate=hotel.rate,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"修改酒店失败：{str(e)}")


@router.delete("/hotel/{hotel_id}", summary="删除酒店")
def delete_hotel(
        hotel_id: int,
        db: Session = Depends(get_db)
):
    try:
        hotel = db.query(DBHotel).filter(DBHotel.id == hotel_id).first()
        if not hotel:
            raise HTTPException(status_code=404, detail="酒店不存在")
        db.delete(hotel)
        db.commit()
        return {"status": "ok", "detail": "酒店删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除酒店失败：{str(e)}")


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


@router.post("/food", response_model=FoodItem, summary="新增美食")
def create_food(
        req: FoodCreateRequest = Body(...),
        db: Session = Depends(get_db)
):
    try:
        food = DBFood(
            name=req.name,
            type=req.type,
            city=req.city,
            phone=req.phone,
            rate=req.rate,
        )
        db.add(food)
        db.commit()
        db.refresh(food)
        return FoodItem(
            id=food.id,
            name=food.name,
            type=food.type,
            city=food.city,
            phone=food.phone,
            rate=food.rate,
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"新增美食失败：{str(e)}")


@router.put("/food/{food_id}", response_model=FoodItem, summary="修改美食信息")
def update_food(
        food_id: int,
        req: FoodUpdateRequest = Body(...),
        db: Session = Depends(get_db)
):
    try:
        food = db.query(DBFood).filter(DBFood.id == food_id).first()
        if not food:
            raise HTTPException(status_code=404, detail="美食不存在")
        if req.name is not None:
            food.name = req.name
        if req.type is not None:
            food.type = req.type
        if req.city is not None:
            food.city = req.city
        if req.phone is not None:
            food.phone = req.phone
        if req.rate is not None:
            food.rate = req.rate
        db.commit()
        db.refresh(food)
        return FoodItem(
            id=food.id,
            name=food.name,
            type=food.type,
            city=food.city,
            phone=food.phone,
            rate=food.rate,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"修改美食失败：{str(e)}")


@router.delete("/food/{food_id}", summary="删除美食")
def delete_food(
        food_id: int,
        db: Session = Depends(get_db)
):
    try:
        food = db.query(DBFood).filter(DBFood.id == food_id).first()
        if not food:
            raise HTTPException(status_code=404, detail="美食不存在")
        db.delete(food)
        db.commit()
        return {"status": "ok", "detail": "美食删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除美食失败：{str(e)}")
