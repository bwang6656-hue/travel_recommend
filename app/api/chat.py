from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.models.models import DBChatHistory
from app.schemas.schemas import ChatMessageRequest, ChatMessageResponse, ChatHistoryResponse, ChatMessageItem
from app.services.rag_service import rag_service

router = APIRouter(prefix="/chat", tags=["智能客服"])

KEYWORD_REPLIES = {
    "推荐": "您好！我可以为您推荐景点。请告诉我您想去哪个城市，喜欢什么类型的景点？比如历史文化、自然风光、美食等。",
    "酒店": "您好！我可以帮您查询酒店信息。请告诉我您想住在哪个城市？",
    "美食": "您好！我可以为您推荐当地美食。请告诉我您在哪个城市，偏好什么类型的美食？",
    "行程": "您好！我可以帮您规划旅游行程。请告诉我您想去哪里、玩几天、有什么偏好？",
    "密码": "您好！如需修改密码，请前往个人中心修改。如果忘记密码，请联系管理员重置。",
    "天气": "您好！我可以在推荐景点时为您查询当地天气。请问您想了解哪个城市的天气？",
    "门票": "您好！我可以在推荐景点时为您查询门票价格。请问您对哪个景点感兴趣？",
    "路线": "您好！我可以为您规划行程路线。请告诉我您的出发地、目的地和游玩天数。",
    "帮助": "您好！我是智能旅游助手，可以帮您：\n1. 推荐景点\n2. 规划行程\n3. 查询酒店美食\n4. 了解天气门票\n请问有什么可以帮您的？",
}


def _keyword_reply(message: str) -> str:
    for keyword, reply in KEYWORD_REPLIES.items():
        if keyword in message:
            return reply
    return ""


@router.post("/message", response_model=ChatMessageResponse, summary="发送客服消息")
def send_chat_message(
        req: ChatMessageRequest,
        db: Session = Depends(get_db)
):
    try:
        user_msg = DBChatHistory(
            user_id=req.user_id,
            role="user",
            content=req.message,
        )
        db.add(user_msg)
        db.commit()
        db.refresh(user_msg)

        reply_text = _keyword_reply(req.message)

        if not reply_text:
            try:
                result = rag_service.plan_itinerary(req.message)
                reply_text = result.get("itinerary", "抱歉，我暂时无法回答这个问题，请稍后再试。")
            except Exception:
                reply_text = "抱歉，智能服务暂时不可用，请稍后再试或联系人工客服。"

        bot_msg = DBChatHistory(
            user_id=req.user_id,
            role="assistant",
            content=reply_text,
        )
        db.add(bot_msg)
        db.commit()
        db.refresh(bot_msg)

        history_records = db.query(DBChatHistory).filter(
            DBChatHistory.user_id == req.user_id
        ).order_by(DBChatHistory.created_at.desc()).limit(20).all()
        history_records.reverse()

        history = [ChatMessageItem.model_validate(r) for r in history_records]

        return ChatMessageResponse(reply=reply_text, history=history)
    except Exception as e:
        db.rollback()
        print(f"客服消息处理失败：{str(e)}")
        raise HTTPException(status_code=500, detail=f"消息处理失败：{str(e)}")


@router.get("/history", response_model=ChatHistoryResponse, summary="获取聊天历史")
def get_chat_history(
        user_id: int = Query(..., ge=1, description="用户ID"),
        limit: int = Query(50, ge=1, le=200, description="返回条数"),
        db: Session = Depends(get_db)
):
    try:
        records = db.query(DBChatHistory).filter(
            DBChatHistory.user_id == user_id
        ).order_by(DBChatHistory.created_at.desc()).limit(limit).all()
        records.reverse()

        messages = [ChatMessageItem.model_validate(r) for r in records]
        return ChatHistoryResponse(user_id=user_id, count=len(messages), messages=messages)
    except Exception as e:
        print(f"获取聊天历史失败：{str(e)}")
        raise HTTPException(status_code=500, detail=f"获取聊天历史失败：{str(e)}")
