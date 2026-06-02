from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
except ImportError:  # pragma: no cover
    TfidfVectorizer = None

try:
    from rank_bm25 import BM25Okapi
except ImportError:  # pragma: no cover
    BM25Okapi = None

try:
    import chromadb
    from chromadb.config import Settings
    from chromadb.utils import embedding_functions
except ImportError:  # pragma: no cover
    chromadb = None
    Settings = None
    embedding_functions = None

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover
    SentenceTransformer = None

ROOT = Path(__file__).resolve().parents[1]
CHUNKS_PATH = ROOT / "data" / "processed" / "chunks.jsonl"
VECTORSTORE_DIR = ROOT / "vectorstore"
VECTORSTORE_COLLECTION = "andrew_ng_chunks"


@dataclass
class RetrievalResult:
    chunk_id: str
    content: str
    metadata: dict
    score: float


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9]+", text.lower())


class HybridRetriever:
    def __init__(self, chunks_path: Path = CHUNKS_PATH) -> None:
        self.chunks_path = chunks_path
        self.records = self._load_records()
        self.vectorizer = None
        self.matrix = None
        self.bm25 = None
        self.tokens: list[list[str]] = []
        self.term_counts: list[Counter[str]] = []
        self.idf: dict[str, float] = {}
        self.client = None
        self.collection = None
        self.id_to_index: dict[str, int] = {}
        if self.records:
            self._fit()
            self._build_vectorstore()

    def _build_vectorstore(self) -> None:
        if chromadb is None or SentenceTransformer is None:
            return

        VECTORSTORE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            client = chromadb.Client(Settings(chroma_db_impl="duckdb+parquet", persist_directory=str(VECTORSTORE_DIR)))
            embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
            self.collection = client.get_or_create_collection(
                name=VECTORSTORE_COLLECTION,
                embedding_function=embedding_function,
            )

            if self.collection.count() != len(self.records):
                client.delete_collection(name=VECTORSTORE_COLLECTION)
                self.collection = client.create_collection(
                    name=VECTORSTORE_COLLECTION,
                    embedding_function=embedding_function,
                )
                ids = [record["chunk_id"] for record in self.records]
                documents = [record["content"] for record in self.records]
                metadatas = [record["metadata"] for record in self.records]
                self.collection.add(ids=ids, documents=documents, metadatas=metadatas)

            self.client = client
            self.id_to_index = {record["chunk_id"]: idx for idx, record in enumerate(self.records)}
        except Exception:
            self.client = None
            self.collection = None

    def _load_records(self) -> list[dict]:
        if not self.chunks_path.exists():
            return []
        records = []
        with self.chunks_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    records.append(json.loads(line))
        return records

    def _fit(self) -> None:
        corpus = [record["content"] for record in self.records]
        self.tokens = [tokenize(text) for text in corpus]
        if TfidfVectorizer is not None:
            self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
            self.matrix = self.vectorizer.fit_transform(corpus)
        else:
            self.term_counts = [Counter(tokens) for tokens in self.tokens]
            document_count = len(self.term_counts)
            document_frequency = Counter(term for tokens in self.tokens for term in set(tokens))
            self.idf = {
                term: math.log((1 + document_count) / (1 + frequency)) + 1
                for term, frequency in document_frequency.items()
            }
        if BM25Okapi is not None:
            self.bm25 = BM25Okapi(self.tokens)

    def search(self, query: str, top_k: int = 5, candidate_k: int = 20) -> list[RetrievalResult]:
        if not self.records:
            return []

        if self.collection is not None:
            dense_scores = self._vector_scores(query, candidate_k)
        elif self.vectorizer is not None and self.matrix is not None:
            query_vector = self.vectorizer.transform([query])
            dense_scores = (self.matrix @ query_vector.T).toarray().ravel()
        else:
            dense_scores = self._fallback_dense_scores(query)
        dense_scores = self._normalize(dense_scores)

        if self.bm25 is not None:
            bm25_scores = self._as_scores(self.bm25.get_scores(tokenize(query)))
        else:
            bm25_scores = self._as_scores(
                [self._keyword_score(query, record["content"]) for record in self.records]
            )
        bm25_scores = self._normalize(bm25_scores)

        metadata_boosts = [self._metadata_bonus(query, record["metadata"]) for record in self.records]

        combined = [
            0.45 * d + 0.45 * b + 0.10 * m
            for d, b, m in zip(dense_scores, bm25_scores, metadata_boosts)
        ]
        candidate_indices = sorted(range(len(combined)), key=lambda index: combined[index], reverse=True)[:candidate_k]
        reranked = self._rerank(query, candidate_indices, combined)
        return [
            RetrievalResult(
                chunk_id=self.records[index]["chunk_id"],
                content=self.records[index]["content"],
                metadata=self.records[index]["metadata"],
                score=float(score),
            )
            for index, score in reranked[:top_k]
        ]

    def _vector_scores(self, query: str, candidate_k: int) -> list[float]:
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=min(candidate_k, len(self.records)),
                include=["distances", "ids"],
            )
            ids = results["ids"][0]
            distances = results["distances"][0]
        except Exception:
            return [0.0 for _ in self.records]

        score_map = {
            item_id: 1.0 / (1.0 + max(0.0, float(distance)))
            for item_id, distance in zip(ids, distances)
        }
        return [score_map.get(record["chunk_id"], 0.0) for record in self.records]

    def _rerank(self, query: str, indices: list[int], base_scores: list[float]) -> list[tuple[int, float]]:
        query_terms = set(tokenize(query))
        reranked = []
        for index in indices:
            content = self.records[index]["content"]
            content_terms = set(tokenize(content))
            overlap = len(query_terms & content_terms)
            length_penalty = math.log(1 + max(1, len(content.split())))
            score = float(base_scores[index] + 0.18 * overlap / length_penalty)
            reranked.append((int(index), score))
        return sorted(reranked, key=lambda item: item[1], reverse=True)

    def _metadata_bonus(self, query: str, metadata: dict) -> float:
        normalized = query.lower()
        bonus = 0.0
        title = str(metadata.get("title", "")).lower()
        speaker = str(metadata.get("speaker", "")).lower()
        topic = str(metadata.get("topic", "")).lower()
        source_type = str(metadata.get("source_type", "")).lower()

        query_tokens = set(tokenize(normalized))
        title_tokens = set(tokenize(title))
        speaker_tokens = set(tokenize(speaker))
        topic_tokens = set(tokenize(topic))

        if {"andrew", "ng"}.issubset(query_tokens):
            if title_tokens & {"andrew", "ng"} or speaker_tokens & {"andrew", "ng"}:
                bonus += 0.12
        if any(keyword in normalized for keyword in ["lecture", "course", "stanford", "deeplearning.ai", "coursera", "research"]):
            if title_tokens & query_tokens or speaker_tokens & query_tokens or topic_tokens & query_tokens:
                bonus += 0.10
        if topic_tokens & query_tokens:
            bonus += 0.10
        if title_tokens & query_tokens:
            bonus += 0.08
        if speaker_tokens & query_tokens:
            bonus += 0.06
        if "lecture" in source_type and any(term in normalized for term in ["course", "lecture", "animation"]):
            bonus += 0.04
        if "paper" in source_type or "publication" in source_type or "research" in source_type:
            bonus += 0.04
        return min(bonus, 0.35)

    @staticmethod
    def _keyword_score(query: str, text: str) -> float:
        q = set(tokenize(query))
        t = set(tokenize(text))
        return len(q & t) / max(1, len(q))

    def _fallback_dense_scores(self, query: str) -> list[float]:
        query_counts = Counter(tokenize(query))
        return [self._cosine_tfidf(query_counts, counts) for counts in self.term_counts]

    def _cosine_tfidf(self, query_counts: Counter[str], doc_counts: Counter[str]) -> float:
        terms = set(query_counts) | set(doc_counts)
        numerator = 0.0
        query_norm = 0.0
        doc_norm = 0.0
        for term in terms:
            idf = self.idf.get(term, 1.0)
            query_weight = query_counts.get(term, 0) * idf
            doc_weight = doc_counts.get(term, 0) * idf
            numerator += query_weight * doc_weight
            query_norm += query_weight * query_weight
            doc_norm += doc_weight * doc_weight
        if query_norm == 0 or doc_norm == 0:
            return 0.0
        return numerator / math.sqrt(query_norm * doc_norm)

    @staticmethod
    def _as_scores(scores) -> list[float]:
        if np is not None and hasattr(scores, "tolist"):
            return scores.tolist()
        return [float(score) for score in scores]

    @staticmethod
    def _normalize(scores) -> list[float]:
        if len(scores) == 0:
            return scores
        min_score = float(min(scores))
        max_score = float(max(scores))
        if max_score == min_score:
            return [0.0 for _ in scores]
        return [(float(score) - min_score) / (max_score - min_score) for score in scores]
