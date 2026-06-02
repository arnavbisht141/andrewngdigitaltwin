from memory.long_term import LongTermMemory


def test_long_term_memory_extracts_goal(tmp_path) -> None:
    memory = LongTermMemory(tmp_path / "memory.sqlite")
    memory.learn_from_turn("Remember that my goal is to become an ML engineer.", "")
    results = memory.search("ML engineer", limit=3)
    assert results


def test_long_term_memory_extracts_name(tmp_path) -> None:
    memory = LongTermMemory(tmp_path / "memory.sqlite")
    memory.learn_from_turn("My name is Arnav.", "")
    profile = memory.profile_summary()
    assert profile["identity"] == "User's name is Arnav."
