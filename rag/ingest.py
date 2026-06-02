from __future__ import annotations

import json
import re
from pathlib import Path

from rag.chunking import chunk_text

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
CHUNKS_PATH = PROCESSED_DIR / "chunks.jsonl"


def clean_text(text: str) -> str:
    text = re.sub(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def infer_metadata(path: Path) -> dict:
    stem = path.stem.replace("_", " ").replace("-", " ").strip()
    sidecar = path.with_suffix(".meta.json")
    if sidecar.exists():
        metadata = json.loads(sidecar.read_text(encoding="utf-8"))
    else:
        metadata = {}
    return {
        "source": str(path),
        "source_type": "local_text",
        "title": stem.title(),
        "year": None,
        "topic": "machine learning",
        "speaker": "Andrew Ng",
        **metadata,
    }


def ingest(raw_dir: Path = RAW_DIR, output_path: Path = CHUNKS_PATH) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    chunks = []
    for path in sorted(raw_dir.rglob("*.txt")):
        text = clean_text(path.read_text(encoding="utf-8"))
        metadata = infer_metadata(path)
        source_id = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(path.relative_to(raw_dir).with_suffix("")))
        chunks.extend(chunk_text(text, source_id, metadata, chunk_size=650, chunk_overlap=150))

    with output_path.open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(
                json.dumps(
                    {
                        "chunk_id": chunk.chunk_id,
                        "content": chunk.content,
                        "metadata": chunk.metadata,
                    },
                    ensure_ascii=True,
                )
                + "\n"
            )
    return len(chunks)


if __name__ == "__main__":
    count = ingest()
    print(f"Wrote {count} chunks to {CHUNKS_PATH}")
