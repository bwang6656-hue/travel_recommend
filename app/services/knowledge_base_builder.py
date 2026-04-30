import os
import json
import pandas as pd
from typing import List, Dict, Tuple, Optional


DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "scenic_spots_30000_llm.csv")
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "saved_models", "knowledge_base")


def _parse_types(type_str: str) -> List[str]:
    if not type_str or pd.isna(type_str):
        return []
    types = set()
    for part in str(type_str).split("|"):
        for sub in part.split(";"):
            sub = sub.strip()
            if sub:
                types.add(sub)
    return list(types)


def _parse_tags(tags_str: str) -> List[str]:
    if not tags_str or pd.isna(tags_str):
        return []
    return [t.strip() for t in str(tags_str).split(",") if t.strip()]


def _price_range(price) -> str:
    try:
        p = float(price)
    except (ValueError, TypeError):
        return "未知"
    if p == 0:
        return "免费"
    elif p <= 30:
        return "低价"
    elif p <= 80:
        return "中等"
    else:
        return "高价"


def build_spot_document(row: pd.Series) -> str:
    parts = [
        f"景点名称：{row['name_zh']}",
        f"所在城市：{row['city']}",
        f"评分：{row['rating']}",
        f"地址：{row.get('address', '未知')}",
        f"类型：{str(row.get('type', '未知')).replace('|', '/').replace(';', '>')}",
        f"门票价格：{row.get('price', '未知')}元",
        f"开放时间：{row.get('open_time', '未知')}",
        f"最佳季节：{row.get('best_season', '未知')}",
        f"拥挤程度：{row.get('crowd_level', '未知')}",
        f"建议游玩时长：{row.get('recommended_duration', '未知')}",
        f"标签：{row.get('tags', '未知')}",
        f"人气值：{row.get('popularity', '未知')}",
    ]
    return "\n".join(parts)


def build_spot_metadata(row: pd.Series) -> Dict:
    types = _parse_types(row.get("type", ""))
    tags = _parse_tags(row.get("tags", ""))
    price = row.get("price", 0)
    try:
        price_val = float(price)
    except (ValueError, TypeError):
        price_val = 0

    return {
        "spot_id": int(row["id"]),
        "name": str(row["name_zh"]),
        "city": str(row["city"]),
        "rating": float(row["rating"]) if not pd.isna(row["rating"]) else 0.0,
        "types": types,
        "tags": tags,
        "price": price_val,
        "price_range": _price_range(price),
        "best_season": str(row.get("best_season", "")),
        "crowd_level": str(row.get("crowd_level", "")),
        "recommended_duration": str(row.get("recommended_duration", "")),
        "popularity": int(row.get("popularity", 0)) if not pd.isna(row.get("popularity")) else 0,
    }


class KnowledgeBaseBuilder:
    def __init__(self, data_path: Optional[str] = None):
        self.data_path = data_path or DATA_PATH
        self.cache_dir = CACHE_DIR
        os.makedirs(self.cache_dir, exist_ok=True)

    def build(self) -> Tuple[List[str], List[Dict]]:
        cache_docs = os.path.join(self.cache_dir, "documents.json")
        cache_meta = os.path.join(self.cache_dir, "metadata.json")

        if os.path.exists(cache_docs) and os.path.exists(cache_meta):
            with open(cache_docs, "r", encoding="utf-8") as f:
                documents = json.load(f)
            with open(cache_meta, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            print(f"[KnowledgeBase] 从缓存加载知识库：{len(documents)} 条文档")
            return documents, metadata

        print(f"[KnowledgeBase] 读取数据文件：{self.data_path}")
        df = pd.read_csv(self.data_path)
        print(f"[KnowledgeBase] 原始数据：{len(df)} 条记录")

        df = df.dropna(subset=["name_zh", "city"])
        df = df[df["name_zh"].str.strip() != ""]
        print(f"[KnowledgeBase] 清洗后数据：{len(df)} 条记录")

        documents = []
        metadata = []

        for _, row in df.iterrows():
            doc = build_spot_document(row)
            meta = build_spot_metadata(row)
            documents.append(doc)
            metadata.append(meta)

        with open(cache_docs, "w", encoding="utf-8") as f:
            json.dump(documents, f, ensure_ascii=False, indent=2)
        with open(cache_meta, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        print(f"[KnowledgeBase] 知识库构建完成：{len(documents)} 条文档，已缓存到 {self.cache_dir}")
        return documents, metadata

    def rebuild(self) -> Tuple[List[str], List[Dict]]:
        cache_docs = os.path.join(self.cache_dir, "documents.json")
        cache_meta = os.path.join(self.cache_dir, "metadata.json")
        if os.path.exists(cache_docs):
            os.remove(cache_docs)
        if os.path.exists(cache_meta):
            os.remove(cache_meta)
        return self.build()


knowledge_base_builder = KnowledgeBaseBuilder()
