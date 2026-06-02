# Architecture

```mermaid
flowchart TD
    User["User"] --> ChatUI["Streamlit Chat UI"]
    ChatUI --> ShortMemory["Short-Term Memory"]
    ChatUI --> LongMemory["Long-Term Memory Retrieval"]
    ChatUI --> Retriever["Hybrid RAG Retrieval"]
    Retriever --> Dense["TF-IDF Dense Similarity"]
    Retriever --> BM25["BM25 Keyword Search"]
    Dense --> Reranker["Local Reranker"]
    BM25 --> Reranker
    ShortMemory --> Prompt["Context + Persona Prompt Builder"]
    LongMemory --> Prompt
    Reranker --> Prompt
    Persona["Andrew Ng Persona YAML"] --> Prompt
    Prompt --> Gemini["Gemini 2.5 Flash"]
    Gemini --> Response["Grounded Persona Response"]
    Response --> ChatUI
    Response --> MemoryUpdate["Memory Update"]
    MemoryUpdate --> LongMemory
```

The system combines two context channels before generation:

- Knowledge context from RAG over local corpus chunks.
- Personal context from short-term and long-term memory.

The persona layer is applied after retrieval so the final response can be both grounded and stylistically consistent.
