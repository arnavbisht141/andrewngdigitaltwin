# Approach and Design Decisions

## Scientist Choice

Andrew Ng is a strong fit because his public teaching corpus is large, his communication style is consistent, and his domain expertise aligns with machine learning and AI education.

## RAG

The ingestion pipeline reads `.txt` files from `data/raw/`, removes simple transcript noise such as timestamps, and creates overlapping chunks of about 900 words with 200 words of overlap. Retrieval combines TF-IDF similarity with BM25 keyword search using a 70/30 weighting, then applies a lightweight reranking step.

This design is intentionally reproducible on a local laptop. For a stronger final submission, the retriever can be upgraded to `BAAI/bge-large-en-v1.5` embeddings and `BAAI/bge-reranker-large` without changing the application boundary.

## Memory

Short-term memory stores the latest 15 messages in the Streamlit session. Long-term memory persists selected user facts in SQLite. The current memory extractor is conservative: it stores explicit user statements such as learning goals, interests, and requests to remember something.

## Persona

The persona profile is stored in YAML. The prompt asks Gemini to use an Andrew Ng-inspired style: structured, practical, warm, beginner-friendly, and evidence-driven. The prompt also prevents unsupported claims and reminds the system that it is an educational emulation.

## Timeline Awareness

The current architecture supports timeline-aware retrieval through metadata fields such as `year` and `source_type`. Adding dated corpus files will allow year-specific responses, such as distinguishing what was publicly known in 2019 from later developments.
