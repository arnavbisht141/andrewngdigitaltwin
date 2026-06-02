from __future__ import annotations

from rag.retrieval import RetrievalResult, tokenize


class LocalReranker:
    """Compatibility wrapper for the retrieval pipeline's local reranking step."""

    def rerank(self, query: str, results: list[RetrievalResult], top_k: int = 5) -> list[RetrievalResult]:
        query_terms = set(tokenize(query))
        scored = []
        for result in results:
            content_terms = set(tokenize(result.content))
            overlap = len(query_terms & content_terms) / max(1, len(query_terms))
            scored.append((result.score + 0.05 * overlap, result))
        return [result for _, result in sorted(scored, key=lambda item: item[0], reverse=True)[:top_k]]
