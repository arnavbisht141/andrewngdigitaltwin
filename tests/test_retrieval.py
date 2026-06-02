import json
from pathlib import Path

from rag.retrieval import HybridRetriever


def test_hybrid_retriever_returns_relevant_chunks(tmp_path: Path) -> None:
    records = [
        {
            "chunk_id": "andrew_ng_0",
            "content": "Andrew Ng is a machine learning educator and the co-founder of Coursera.",
            "metadata": {
                "title": "Andrew Ng Bio",
                "speaker": "Andrew Ng",
                "year": 2020,
                "source_type": "bio",
            },
        },
        {
            "chunk_id": "deep_learning_0",
            "content": "Deep learning is a subset of machine learning that uses neural networks.",
            "metadata": {
                "title": "Deep Learning Overview",
                "speaker": "Researcher",
                "year": 2018,
                "source_type": "article",
            },
        },
    ]
    chunks_path = tmp_path / "chunks.jsonl"
    with chunks_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")

    retriever = HybridRetriever(chunks_path=chunks_path)
    results = retriever.search("What is Andrew Ng known for?", top_k=2)

    assert len(results) == 2
    assert any("Andrew Ng" in result.content for result in results)
    assert results[0].score >= results[1].score
