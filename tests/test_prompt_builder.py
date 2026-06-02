from persona.prompt_builder import build_prompt
from rag.retrieval import RetrievalResult


def test_prompt_contains_persona_and_sources() -> None:
    prompt = build_prompt(
        user_query="Explain gradient descent",
        conversation_history=[],
        retrieved_chunks=[
            RetrievalResult(
                chunk_id="c1",
                content="Gradient descent improves parameters using gradients.",
                metadata={"title": "Lecture", "source_type": "lecture"},
                score=1.0,
            )
        ],
        memories=["User is learning ML."],
    )
    assert "Andrew Ng" in prompt
    assert "Gradient descent" in prompt
    assert "User is learning ML" in prompt
