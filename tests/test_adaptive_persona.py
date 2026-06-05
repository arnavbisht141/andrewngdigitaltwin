from persona.prompt_builder import build_prompt


def test_build_prompt_with_roles() -> None:
    # 1. Test Student role
    prompt_student = build_prompt(
        user_query="Gradient descent",
        conversation_history=[],
        retrieved_chunks=[],
        memories=[],
        user_role="Student"
    )
    assert "visual intuition" in prompt_student
    assert "encouraging" in prompt_student
    
    # 2. Test Scientist/Researcher role
    prompt_researcher = build_prompt(
        user_query="Gradient descent",
        conversation_history=[],
        retrieved_chunks=[],
        memories=[],
        user_role="Researcher"
    )
    assert "academic rigor" in prompt_researcher
    assert "mathematical derivations" in prompt_researcher
    
    # 3. Test Engineer role
    prompt_engineer = build_prompt(
        user_query="Gradient descent",
        conversation_history=[],
        retrieved_chunks=[],
        memories=[],
        user_role="Engineer"
    )
    assert "practical diagnostics" in prompt_engineer
    assert "MLOps" in prompt_engineer
    
    # 4. Test Executive role
    prompt_executive = build_prompt(
        user_query="Gradient descent",
        conversation_history=[],
        retrieved_chunks=[],
        memories=[],
        user_role="Executive"
    )
    assert "commercial applicability" in prompt_executive
    assert "workflow integration" in prompt_executive
