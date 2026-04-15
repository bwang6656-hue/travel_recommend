import os
from typing import List, Dict, Optional
import dashscope  # 通义千问官方SDK
from app.config.config import QWEN_API_KEY, QWEN_MODEL

class AITripGenerator:
    def __init__(self):
        # 从配置读取千问API Key
        self.qwen_api_key = QWEN_API_KEY
        # 全局设置千问API Key
        dashscope.api_key = self.qwen_api_key

        self.model = QWEN_MODEL

    def generate_itinerary(
            self,
            spots: List[Dict],  # 景点列表：[{"name": "外滩", "city": "上海", "type": "景点"}]
            days: int = 1,  # 行程天数
            preference: Optional[str] = None  # 游玩偏好
    ) -> str:
        """核心方法：调用千问生成行程文案"""
        # 1. 构造景点信息字符串
        spot_info = "\n".join([
            f"- {spot['name']}（{spot['city']}，类型：{spot.get('type', '未知')}）"
            for spot in spots
        ])

        # 2. 构造行程生成的Prompt（口语化，适合旅游规划）
        prompt = f"""
        你是专业的旅游行程规划师，请根据以下信息为用户生成{days}天的游玩行程：
        【景点列表】
        {spot_info}

        【生成要求】
        1. 按天数拆分，每天明确上午/下午/晚上的行程（1天可灵活调整时段）；
        2. 行程顺序合理：同城市的景点集中安排，人文和自然景观穿插；
        3. 推荐当地特色美食（比如上海生煎、北京烤鸭）；
        4. 语言自然口语化，避免生硬的列表形式；
        5. 优先满足用户偏好：{preference if preference else '无特殊偏好'}。

        【示例输出（1天行程）】
        第一天上午去外滩欣赏黄浦江两岸风光，下午逛豫园感受江南园林韵味，晚上到南京路步行街吃上海生煎，体验魔都的烟火气～
        """

        # 3. 调用通义千问API（核心逻辑，无client属性）
        try:
            # 千问的调用方式：直接用dashscope.Generation.call
            response = dashscope.Generation.call(
                model=self.model,  # 千问模型名
                prompt=prompt,  # 提示词
                temperature=0.7,  # 随机性（0-1，越小越固定）
                max_tokens=500,  # 最大生成字数
                result_format="text"  # 返回纯文本，简化处理
            )

            # 校验响应是否成功
            if response.status_code == 200:
                # 提取千问返回的行程文案
                itinerary_text = response.output.text.strip()
                return itinerary_text
            else:
                # 千问API返回错误
                return f"行程生成失败：{response.message[:50]}"

        except Exception as e:
            # 捕获其他异常（如网络、密钥错误）
            error_msg = str(e)[:50]
            return f"行程生成失败，请稍后重试（错误：{error_msg}）"


# 全局单例实例
ai_trip_generator = AITripGenerator()
