import os
import json
import numpy as np
import faiss
import torch
from typing import List, Dict, Tuple, Optional
from sentence_transformers import SentenceTransformer
from app.services.knowledge_base_builder import knowledge_base_builder

FAISS_INDEX_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "saved_models", "faiss_index")
LOCAL_EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
EMBEDDING_DIM = 512
BATCH_SIZE = 256


class VectorStoreService:
    def __init__(self):
        self.index_dir = FAISS_INDEX_DIR
        os.makedirs(self.index_dir, exist_ok=True)
        self.index: Optional[faiss.IndexFlatIP] = None
        self.documents: List[str] = []
        self.metadata: List[Dict] = []
        self._initialized = False
        self._embed_model: Optional[SentenceTransformer] = None

    def _get_embed_model(self) -> SentenceTransformer:
        if self._embed_model is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"[VectorStore] 加载Embedding模型: {LOCAL_EMBEDDING_MODEL} (设备: {device})")
            self._embed_model = SentenceTransformer(LOCAL_EMBEDDING_MODEL, device=device)
            print(f"[VectorStore] 模型加载完成，向量维度: {self._embed_model.get_sentence_embedding_dimension()}")
        return self._embed_model

    def _index_path(self) -> str:
        return os.path.join(self.index_dir, "spots.index")

    def _docs_path(self) -> str:
        return os.path.join(self.index_dir, "docs.json")

    def _meta_path(self) -> str:
        return os.path.join(self.index_dir, "meta.json")

    def _emb_path(self) -> str:
        return os.path.join(self.index_dir, "embeddings.npy")

    def _embed_texts(self, texts: List[str], show_progress: bool = True) -> np.ndarray:
        model = self._get_embed_model()
        embeddings = model.encode(
            texts,
            batch_size=BATCH_SIZE,
            show_progress_bar=show_progress and len(texts) > 100,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return embeddings

    def build_index(self, force_rebuild: bool = False):
        if not force_rebuild and self._load_index():
            self._initialized = True
            print(f"[VectorStore] 从磁盘加载FAISS索引：{self.index.ntotal} 条向量")
            return

        print("[VectorStore] 开始构建FAISS索引...")
        documents, metadata = knowledge_base_builder.build()
        self.documents = documents
        self.metadata = metadata

        emb_cache = self._emb_path()
        emb_array = None

        if not force_rebuild and os.path.exists(emb_cache):
            print(f"[VectorStore] 从缓存加载Embedding向量...")
            emb_array = np.load(emb_cache)
            if emb_array.shape[0] != len(documents):
                print(f"[VectorStore] 缓存向量数({emb_array.shape[0]})与文档数({len(documents)})不匹配，重新生成")
                emb_array = None
            else:
                print(f"[VectorStore] 加载完成：{emb_array.shape[0]} 条向量")

        if emb_array is None:
            print(f"[VectorStore] 生成Embedding向量（{len(documents)} 条文档）...")
            emb_array = self._embed_texts(documents, show_progress=True)
            np.save(emb_cache, emb_array)
            print(f"[VectorStore] Embedding向量已缓存到 {emb_cache}")

        norms = np.linalg.norm(emb_array, axis=1, keepdims=True)
        norms[norms == 0] = 1
        emb_array = emb_array / norms

        zero_mask = np.all(emb_array == 0, axis=1)
        valid_mask = ~zero_mask
        valid_count = int(valid_mask.sum())
        if valid_count < emb_array.shape[0]:
            print(f"[VectorStore] 过滤零向量：{emb_array.shape[0] - valid_count} 条无效，保留 {valid_count} 条")

        self.index = faiss.IndexFlatIP(emb_array.shape[1])
        self.index.add(emb_array[valid_mask])

        self._save_index()
        self._initialized = True
        print(f"[VectorStore] FAISS索引构建完成：{self.index.ntotal} 条向量")

    def _save_index(self):
        faiss.write_index(self.index, self._index_path())
        with open(self._docs_path(), "w", encoding="utf-8") as f:
            json.dump(self.documents, f, ensure_ascii=False)
        with open(self._meta_path(), "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, ensure_ascii=False)
        print(f"[VectorStore] 索引已保存到 {self.index_dir}")

    def _load_index(self) -> bool:
        index_path = self._index_path()
        docs_path = self._docs_path()
        meta_path = self._meta_path()

        if not all(os.path.exists(p) for p in [index_path, docs_path, meta_path]):
            return False

        try:
            self.index = faiss.read_index(index_path)
            with open(docs_path, "r", encoding="utf-8") as f:
                self.documents = json.load(f)
            with open(meta_path, "r", encoding="utf-8") as f:
                self.metadata = json.load(f)
            return True
        except Exception as e:
            print(f"[VectorStore] 加载索引失败: {e}")
            return False

    def search(
        self,
        query: str,
        top_k: int = 20,
        city_filter: Optional[str] = None,
        season_filter: Optional[str] = None,
        price_max: Optional[float] = None,
    ) -> List[Dict]:
        if not self._initialized or self.index is None:
            print("[VectorStore] 索引未初始化，请先调用 build_index()")
            return []

        query_vec = self._embed_texts([query], show_progress=False)
        if query_vec is None or len(query_vec) == 0:
            return []

        search_k = min(top_k * 5, self.index.ntotal)
        scores, indices = self.index.search(query_vec, search_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue

            meta = self.metadata[idx]

            if city_filter and meta.get("city") != city_filter:
                continue
            if season_filter and season_filter not in meta.get("best_season", ""):
                continue
            if price_max is not None and meta.get("price", float("inf")) > price_max:
                continue

            results.append({
                "document": self.documents[idx],
                "metadata": meta,
                "score": float(score),
            })

            if len(results) >= top_k:
                break

        return results

    def get_spots_by_city(self, city: str, top_k: int = 50) -> List[Dict]:
        if not self._initialized:
            return []

        results = []
        for i, meta in enumerate(self.metadata):
            if meta.get("city") == city:
                results.append({
                    "document": self.documents[i],
                    "metadata": meta,
                    "score": 1.0,
                })
                if len(results) >= top_k:
                    break

        results.sort(key=lambda x: x["metadata"].get("rating", 0), reverse=True)
        return results


vector_store_service = VectorStoreService()
