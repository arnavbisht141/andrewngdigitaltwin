# Digital Twin of Andrew Ng

This project builds an interactive digital twin of Andrew Ng for the AIMS DTU Summer Project 2026 assignment. It combines persona prompting, retrieval augmented generation, short-term chat history, persistent long-term memory, and a Streamlit demo.

## What It Does

- Answers ML and AI questions in an Andrew Ng-inspired teaching style.
- Retrieves grounded context from local Andrew Ng source material.
- Maintains short-term memory within a session.
- Stores long-term user facts in SQLite across sessions.
- Shows retrieved sources and remembered facts in the UI.
- Uses Gemini 2.5 Flash for final response generation.

This is an educational emulation. It is not Andrew Ng and should not be presented as the real person.

## Project Structure

```text
app/                 Streamlit app and chat orchestration
rag/                 Corpus ingestion, chunking, retrieval, reranking
memory/              Short-term and long-term memory
persona/             Andrew Ng profile and prompt builder
data/raw/            Source text files for ingestion
data/processed/      Generated chunk JSONL
vectorstore/         Local retrieval artifacts
docs/                Architecture and design docs
conversations/       Ten sample conversations
tests/               Unit tests
```

## Setup With uv

This repository includes a `pyproject.toml` and `uv.lock`. 

## Corpus Expansion

The starter corpus in `data/raw/` is intentionally small so the repository is reproducible. To improve evaluation quality, add transcripts, articles, and lecture notes as `.txt` files in `data/raw/`, then rerun:

```bash
python -m rag.ingest
```

Recommended sources include DeepLearning.AI articles, Stanford CS229 notes, public lecture transcripts, podcast transcripts, and interviews.

## Design Choices

- Gemini 2.5 Flash is used for generation to match the assignment.
- Retrieval uses dense TF-IDF similarity plus BM25 keyword matching, then a lightweight local reranker. If heavier embedding dependencies are available, the structure can be extended without changing the UI.
- Long-term memory uses SQLite for reproducible local persistence.
- Persona is configured in YAML so it can be audited and refined without changing code.

See [docs/approach.md](docs/approach.md) and [docs/architecture.md](docs/architecture.md).

