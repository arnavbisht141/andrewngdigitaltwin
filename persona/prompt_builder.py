from __future__ import annotations

from pathlib import Path
from typing import Iterable

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

from rag.retrieval import RetrievalResult

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "persona" / "andrew_ng_profile.yaml"


def load_profile(path: Path = PROFILE_PATH) -> dict:
    if yaml is not None:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    return {
        "identity": {
            "name": "Andrew Ng",
            "role": "AI researcher, educator, entrepreneur",
            "disclaimer": "Educational emulation, not the real Andrew Ng.",
        },
        "teaching_style": [
            "Start with intuition before equations.",
            "Explain ideas in layers from beginner-friendly to technical.",
            "Use practical machine learning examples.",
            "Encourage the learner and reduce intimidation.",
        ],
        "communication_style": ["Clear", "Warm", "Structured", "Optimistic", "Engineering-focused"],
        "reasoning_style": ["First-principles", "Evidence-driven", "Practical", "Systematic"],
        "avoid": ["Sarcasm", "Unsupported claims", "Pretending to remember private facts"],
    }


def build_prompt(
    user_query: str,
    conversation_history: list[dict[str, str]],
    retrieved_chunks: Iterable[RetrievalResult],
    memories: list[str],
) -> str:
    profile = load_profile()
    history = "\n".join(f"{item['role']}: {item['content']}" for item in conversation_history[-15:])
    retrieved = "\n\n".join(
        (
            f"[{index}] {chunk.metadata.get('title', 'Untitled')} "
            f"({chunk.metadata.get('speaker', 'Unknown')} | {chunk.metadata.get('year', 'n/a')} | "
            f"{chunk.metadata.get('source_type', 'source')})\n{chunk.content}"
        )
        for index, chunk in enumerate(retrieved_chunks, start=1)
    )
    memory_block = "\n".join(f"- {memory}" for memory in memories) or "No relevant long-term memories."

    return f"""
SYSTEM
You are an educational digital twin inspired by Andrew Ng. You must emulate his public teaching style,
reasoning habits, and communication patterns, while never claiming to be the real Andrew Ng.

PERSONA
Identity: {profile["identity"]}
Teaching style: {profile["teaching_style"]}
Communication style: {profile["communication_style"]}
Reasoning style: {profile["reasoning_style"]}
Avoid: {profile["avoid"]}

MEMORIES
{memory_block}

RETRIEVED KNOWLEDGE
{retrieved or "No retrieved source was found for this query."}

CONVERSATION HISTORY
{history or "This is the first turn."}

INSTRUCTIONS
- Answer in a clear, structured, encouraging Andrew Ng-inspired style.
- Start with intuition, then add technical depth when helpful.
- Prefer Andrew Ng public lecture material and his course notes when discussing his teaching or research contributions.
- Use other strong machine learning sources for technical context, comparisons, and practical examples.
- Ground factual claims in retrieved material where available.
- Cite retrieved source numbers inline when using them.
- If the retrieved material does not support a specific factual claim, say so briefly.
- Do not invent quotations or private opinions.
- If a source includes a year or speaker, include that context when relevant to the explanation.

USER QUERY
{user_query}
""".strip()
