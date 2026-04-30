import os
from typing import List, Dict, Optional
import dashscope
from app.config.config import QWEN_API_KEY, QWEN_MODEL


class AITripGenerator:
    def __init__(self):
        self.qwen_api_key = QWEN_API_KEY
        dashscope.api_key = self.qwen_api_key
        self.model = QWEN_MODEL

    def generate_itinerary(
            self,
            spots: List[Dict],
            days: int = 1,
            preference: Optional[str] = None
    ) -> str:
        spot_info = "\n".join([
            f"- {spot['name']}（{spot['city']}，类型：{spot.get('type', '未知')}）"
            for spot in spots
        ])

        messages = [
            {
                "role": "system",
                "content": "你是一位专业的旅游行程规划师。请根据用户提供的景点信息，生成合理、详细的行程方案。语言自然口语化，像朋友给建议一样。"
            },
            {
                "role": "user",
                "content": f"""请根据以下信息为用户生成{days}天的游玩行程：

【景点列表】
{spot_info}

【生成要求】
1. 按天数拆分，每天明确上午/下午/晚上的行程；
2. 行程顺序合理：同城市的景点集中安排，人文和自然景观穿插；
3. 推荐当地特色美食；
4. 语言自然口语化，避免生硬的列表形式；
5. 优先满足用户偏好：{preference if preference else '无特殊偏好'}。"""
            }
        ]

        try:
            response = dashscope.Generation.call(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
                result_format="message",
            )

            if response.status_code == 200:
                itinerary_text = response.output.choices[0].message.content.strip()
                return itinerary_text
            else:
                return f"行程生成失败：{response.message[:50]}"

        except Exception as e:
            error_msg = str(e)[:50]
            return f"行程生成失败，请稍后重试（错误：{error_msg}）"


ai_trip_generator = AITripGenerator()
