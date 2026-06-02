from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Chunk:
    chunk_id: str
    content: str
    metadata: dict


def chunk_text(
    text: str,
    source_id: str,
    metadata: dict,
    chunk_size: int = 900,
    chunk_overlap: int = 200,
) -> list[Chunk]:
    words = text.split()
    if not words:
        return []

    chunks: list[Chunk] = []
    start = 0
    index = 0
    step = max(1, chunk_size - chunk_overlap)
    while start < len(words):
        end = min(start + chunk_size, len(words))
        content = " ".join(words[start:end])
        chunks.append(
            Chunk(
                chunk_id=f"{source_id}:{index}",
                content=content,
                metadata={**metadata, "chunk_index": index},
            )
        )
        if end == len(words):
            break
        start += step
        index += 1
    return chunks
