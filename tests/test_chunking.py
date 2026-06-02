from rag.chunking import chunk_text


def test_chunk_text_uses_overlap() -> None:
    text = " ".join(str(i) for i in range(20))
    chunks = chunk_text(text, "source", {"title": "Test"}, chunk_size=10, chunk_overlap=2)
    assert len(chunks) == 3
    assert chunks[0].content.split()[-2:] == chunks[1].content.split()[:2]
