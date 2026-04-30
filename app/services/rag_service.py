import json
import re
import dashscope
from typing import Dict, List, Optional, Any
from app.config.config import QWEN_API_KEY, QWEN_MODEL
from app.services.vector_store_service import vector_store_service

dashscope.api_key = QWEN_API_KEY

CITY_KEYWORDS = {
    "北京": ["北京", "京城", "帝都", "北平"],
    "上海": ["上海", "魔都", "申城"],
    "广州": ["广州", "羊城", "花城"],
    "深圳": ["深圳", "鹏城"],
    "成都": ["成都", "蓉城", "天府"],
    "杭州": ["杭州", "杭城", "临安"],
    "西安": ["西安", "长安", "镐京"],
    "南京": ["南京", "金陵", "建康"],
    "重庆": ["重庆", "山城", "渝"],
    "武汉": ["武汉", "江城"],
    "长沙": ["长沙", "星城"],
    "苏州": ["苏州", "姑苏"],
    "厦门": ["厦门", "鹭岛"],
    "青岛": ["青岛"],
    "大连": ["大连"],
    "昆明": ["昆明", "春城"],
    "丽江": ["丽江"],
    "三亚": ["三亚", "海南"],
    "拉萨": ["拉萨", "西藏"],
    "天津": ["天津", "津门"],
    "哈尔滨": ["哈尔滨", "冰城"],
    "沈阳": ["沈阳", "盛京"],
    "济南": ["济南", "泉城"],
    "郑州": ["郑州"],
    "福州": ["福州", "榕城"],
    "桂林": ["桂林"],
    "黄山": ["黄山"],
    "张家界": ["张家界"],
    "九寨沟": ["九寨沟"],
}

PREFERENCE_KEYWORDS = {
    "历史文化": ["历史", "文化", "古迹", "古建筑", "博物馆", "遗产", "文物", "传统", "古镇"],
    "自然风光": ["自然", "山水", "风景", "风光", "山水", "湖", "山", "海", "森林", "草原", "瀑布"],
    "美食": ["美食", "小吃", "吃货", "餐饮", "特色菜", "当地菜", "好吃"],
    "亲子": ["亲子", "儿童", "小孩", "孩子", "家庭", "带娃", "小朋友"],
    "情侣": ["情侣", "浪漫", "约会", "二人世界", "蜜月"],
    "休闲度假": ["休闲", "度假", "放松", "慢生活", "养生", "温泉"],
    "户外运动": ["徒步", "登山", "骑行", "户外", "探险", "运动", "攀岩"],
    "摄影": ["摄影", "拍照", "打卡", "网红", "出片"],
    "夜景": ["夜景", "夜游", "灯光", "夜市"],
    "购物": ["购物", "逛街", "商场", "特产", "纪念品"],
}

SEASON_KEYWORDS = {
    "春季": ["春天", "春季", "3月", "4月", "5月", "踏青"],
    "夏季": ["夏天", "夏季", "6月", "7月", "8月", "避暑"],
    "秋季": ["秋天", "秋季", "9月", "10月", "11月", "赏秋", "赏红叶"],
    "冬季": ["冬天", "冬季", "12月", "1月", "2月", "滑雪", "看雪"],
}

BUDGET_KEYWORDS = {
    "低": ["预算不高", "省钱", "便宜", "经济", "穷游", "低价", "免费", "不贵"],
    "中": ["适中", "一般", "中等"],
    "高": ["豪华", "高端", "奢侈", "贵", "不在乎价格"],
}


INTENT_SYSTEM_PROMPT = """你是一个旅游需求分析助手。你的任务是从用户的自然语言描述中提取结构化的旅游需求信息。

请从用户输入中提取以下信息，并以JSON格式返回：
{
    "city": "城市名称（如北京、上海），未提及则为null",
    "days": "行程天数（整数），未提及则为null",
    "preference": "用户偏好关键词（如历史文化、自然风光、美食、亲子、情侣等），未提及则为null",
    "season": "出行季节（如春季、夏季、秋季、冬季），未提及则为null",
    "budget": "预算级别（低/中/高），未提及则为null",
    "crowd_preference": "拥挤度偏好（低/中/高），未提及则为null"
}

只返回JSON，不要返回其他内容。"""


ITINERARY_SYSTEM_PROMPT = """你是一位专业的旅游行程规划师。你需要根据提供的景点信息，为用户生成详细、合理的行程方案。

规划原则：
1. 按天数拆分行程，每天安排上午/下午/晚上的活动
2. 同一区域或相近的景点安排在同一天
3. 考虑景点的开放时间、建议游玩时长、拥挤程度
4. 合理搭配不同类型的景点（自然+人文+休闲）
5. 推荐当地特色美食和体验
6. 语言自然亲切，像朋友给建议一样
7. 必须基于提供的景点信息进行推荐，不要编造不存在的景点
8. 如果景点信息中有门票价格、开放时间等，请在行程中提及"""


class RAGService:
    def __init__(self):
        self.model = QWEN_MODEL

    def _call_llm(self, messages: List[Dict], temperature: float = 0.7, max_tokens: int = 2000) -> str:
        try:
            response = dashscope.Generation.call(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                result_format="message",
            )
            if response.status_code == 200:
                return response.output.choices[0].message.content
            else:
                print(f"[RAG] LLM调用失败: {response.message}")
                return ""
        except Exception as e:
            print(f"[RAG] LLM调用异常: {e}")
            return ""

    def extract_intent_rule_based(self, query: str) -> Dict[str, Any]:
        intent = {
            "city": None,
            "days": None,
            "preference": None,
            "season": None,
            "budget": None,
            "crowd_preference": None,
        }

        for city, keywords in CITY_KEYWORDS.items():
            for kw in keywords:
                if kw in query:
                    intent["city"] = city
                    break
            if intent["city"]:
                break

        day_match = re.search(r"(\d+)\s*[天日]", query)
        if day_match:
            intent["days"] = int(day_match.group(1))

        for pref, keywords in PREFERENCE_KEYWORDS.items():
            for kw in keywords:
                if kw in query:
                    intent["preference"] = pref
                    break
            if intent["preference"]:
                break

        for season, keywords in SEASON_KEYWORDS.items():
            for kw in keywords:
                if kw in query:
                    intent["season"] = season
                    break
            if intent["season"]:
                break

        for budget, keywords in BUDGET_KEYWORDS.items():
            for kw in keywords:
                if kw in query:
                    intent["budget"] = budget
                    break
            if intent["budget"]:
                break

        if "人少" in query or "清静" in query or "安静" in query:
            intent["crowd_preference"] = "低"
        elif "热闹" in query or "人气" in query:
            intent["crowd_preference"] = "高"

        return intent

    def extract_intent(self, query: str) -> Dict[str, Any]:
        rule_intent = self.extract_intent_rule_based(query)

        messages = [
            {"role": "system", "content": INTENT_SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ]
        result = self._call_llm(messages, temperature=0.1, max_tokens=500)

        if result:
            try:
                cleaned = result.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[-1]
                    cleaned = cleaned.rsplit("```", 1)[0]
                llm_intent = json.loads(cleaned)

                for key in ["city", "days", "preference", "season", "budget", "crowd_preference"]:
                    if llm_intent.get(key) and not rule_intent.get(key):
                        rule_intent[key] = llm_intent[key]
            except (json.JSONDecodeError, IndexError):
                pass

        return rule_intent

    def retrieve_spots(self, intent: Dict[str, Any], query: str, top_k: int = 30) -> List[Dict]:
        city = intent.get("city")
        season = intent.get("season")
        budget = intent.get("budget")

        price_max = None
        if budget == "低":
            price_max = 30
        elif budget == "中":
            price_max = 80

        if city:
            city_spots = vector_store_service.get_spots_by_city(city, top_k=top_k * 2)
            semantic_spots = vector_store_service.search(
                query, top_k=top_k, city_filter=city,
                season_filter=season, price_max=price_max,
            )

            seen_ids = set()
            merged = []
            for spot in semantic_spots + city_spots:
                sid = spot["metadata"].get("spot_id")
                if sid not in seen_ids:
                    seen_ids.add(sid)
                    merged.append(spot)

            merged.sort(key=lambda x: (x.get("score", 0) + x["metadata"].get("rating", 0) / 5.0 * 0.5), reverse=True)
            return merged[:top_k]
        else:
            return vector_store_service.search(
                query, top_k=top_k,
                season_filter=season, price_max=price_max,
            )

    def _format_context(self, spots: List[Dict], intent: Dict) -> str:
        if not spots:
            return "暂无匹配的景点信息。"

        city = intent.get("city") or "未指定"
        days = intent.get("days") or "未指定"
        preference = intent.get("preference") or "无特殊偏好"
        season = intent.get("season") or "未指定"

        header = f"用户需求：城市={city}，天数={days}，偏好={preference}，季节={season}\n\n"
        header += "以下是从知识库中检索到的相关景点信息：\n\n"

        spot_details = []
        for i, spot in enumerate(spots[:20], 1):
            doc = spot["document"]
            score = spot.get("score", 0)
            spot_details.append(f"【景点{i}】（相关度：{score:.3f}）\n{doc}\n")

        return header + "\n".join(spot_details)

    def _generate_fallback_itinerary(self, spots: List[Dict], intent: Dict) -> str:
        city = intent.get("city") or "目的地"
        days = intent.get("days") or 2
        preference = intent.get("preference") or ""

        lines = [f"为您推荐{city}{days}天行程方案（{preference}主题）：\n"]

        top_spots = spots[:days * 3]
        for day in range(1, days + 1):
            lines.append(f"【第{day}天】")
            day_spots = top_spots[(day - 1) * 3: day * 3]
            for period, spot in zip(["上午", "下午", "晚上"], day_spots):
                meta = spot["metadata"]
                name = meta.get("name", "未知景点")
                price = meta.get("price", 0)
                duration = meta.get("recommended_duration", "")
                price_str = f"门票{int(price)}元" if price > 0 else "免费"
                duration_str = f"，建议游玩{duration}" if duration else ""
                lines.append(f"  {period}：{name}（{price_str}{duration_str}）")
            lines.append("")

        if preference:
            lines.append(f"温馨提示：以上景点均与您的偏好「{preference}」相关，建议提前查看开放时间。")

        return "\n".join(lines)

    def plan_itinerary(self, query: str) -> Dict[str, Any]:
        print(f"[RAG] 收到查询: {query}")

        intent = self.extract_intent(query)
        print(f"[RAG] 提取意图: {intent}")

        spots = self.retrieve_spots(intent, query)
        print(f"[RAG] 检索到 {len(spots)} 个相关景点")

        context = self._format_context(spots, intent)

        days_str = str(intent.get("days", 2)) if intent.get("days") else "2"

        user_message = f"用户需求：{query}\n\n{context}\n\n请根据以上景点信息，为用户规划{days_str}天的旅游行程。"

        messages = [
            {"role": "system", "content": ITINERARY_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        itinerary = self._call_llm(messages, temperature=0.7, max_tokens=2000)

        if not itinerary:
            print("[RAG] LLM不可用，使用模板生成行程")
            itinerary = self._generate_fallback_itinerary(spots, intent)

        related_spots = []
        for spot in spots[:10]:
            meta = spot["metadata"]
            related_spots.append({
                "spot_id": meta.get("spot_id"),
                "name": meta.get("name"),
                "city": meta.get("city"),
                "rating": meta.get("rating"),
                "price": meta.get("price"),
                "best_season": meta.get("best_season"),
                "recommended_duration": meta.get("recommended_duration"),
                "tags": meta.get("tags", []),
            })

        return {
            "query": query,
            "itinerary": itinerary,
            "related_spots": related_spots,
            "days": intent.get("days") or 2,
            "city": intent.get("city"),
            "preference": intent.get("preference"),
            "intent": intent,
        }


rag_service = RAGService()
