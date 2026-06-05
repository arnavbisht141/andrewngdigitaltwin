import json
from pathlib import Path
from rag.retrieval import HybridRetriever


def test_hybrid_retriever_filters_by_threshold(tmp_path: Path) -> None:
    records = [
        {
            "chunk_id": "c1",
            "content": "Deep learning uses neural networks.",
            "metadata": {"title": "DL Overview", "source_type": "article"},
        },
        {
            "chunk_id": "c2",
            "content": "Some completely unrelated random text content here.",
            "metadata": {"title": "Random", "source_type": "article"},
        },
    ]
    chunks_path = tmp_path / "chunks.jsonl"
    with chunks_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")
            
    retriever = HybridRetriever(chunks_path=chunks_path)
    
    # 1. Search without threshold
    results_all = retriever.search("deep learning", top_k=2, min_score=0.0)
    assert len(results_all) == 2
    
    # 2. Search with high threshold (should drop c2)
    results_filtered = retriever.search("deep learning", top_k=2, min_score=0.15)
    assert len(results_filtered) == 1
    assert results_filtered[0].chunk_id == "c1"
