from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.models.models import DBFeedback, DBUser
from app.schemas.schemas import FeedbackRequest, FeedbackResponse, FeedbackListResponse

router = APIRouter(prefix="/feedback", tags=["意见反馈"])


@router.post("", response_model=FeedbackResponse, summary="提交意见反馈")
def submit_feedback(
        req: FeedbackRequest,
        db: Session = Depends(get_db)
):
    try:
        username = req.username
        if req.user_id and not username:
            user = db.query(DBUser).filter(DBUser.id == req.user_id).first()
            if user:
                username = user.username

        feedback = DBFeedback(
            user_id=req.user_id,
            username=username,
            content=req.content,
            type=req.type or "suggestion",
        )
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        return FeedbackResponse.model_validate(feedback)
    except Exception as e:
        db.rollback()
        print(f"提交反馈失败：{str(e)}")
        raise HTTPException(status_code=500, detail=f"提交反馈失败：{str(e)}")


@router.get("", response_model=FeedbackListResponse, summary="查询用户反馈记录")
def get_user_feedbacks(
        user_id: int = Query(..., ge=1, description="用户ID"),
        db: Session = Depends(get_db)
):
    try:
        user = db.query(DBUser).filter(DBUser.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        feedbacks = db.query(DBFeedback).filter(
            DBFeedback.user_id == user_id
        ).order_by(DBFeedback.create_time.desc()).all()
        items = [FeedbackResponse.model_validate(f) for f in feedbacks]
        return FeedbackListResponse(count=len(items), feedbacks=items)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询反馈失败：{str(e)}")
