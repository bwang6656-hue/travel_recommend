from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.models.models import DBFeedback
from app.schemas.schemas import FeedbackRequest, FeedbackResponse

router = APIRouter(prefix="/feedback", tags=["意见反馈"])

@router.post("", response_model=FeedbackResponse, summary="提交意见反馈")
def submit_feedback(
        req: FeedbackRequest,
        db: Session = Depends(get_db)
):
    try:
        feedback = DBFeedback(
            user_id=req.user_id,
            content=req.content,
            contact=req.contact,
        )
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        return FeedbackResponse.model_validate(feedback)
    except Exception as e:
        db.rollback()
        print(f"提交反馈失败：{str(e)}")
        raise HTTPException(status_code=500, detail=f"提交反馈失败：{str(e)}")
