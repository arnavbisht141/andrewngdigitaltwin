from pathlib import Path
from memory.long_term import LongTermMemory


def test_memory_crud_operations(tmp_path: Path) -> None:
    db_file = tmp_path / "test_memory.sqlite"
    memory = LongTermMemory(db_path=db_file)
    
    # 1. Add manual records
    memory.add_manual_record("User wants to learn calculus.", kind="learning", importance=0.8)
    memory.add_manual_record("User likes dark mode.", kind="preference", importance=0.6)
    
    records = memory.recent_records()
    assert len(records) == 2
    
    calc_record = [r for r in records if "calculus" in r.fact][0]
    pref_record = [r for r in records if "dark mode" in r.fact][0]
    
    # 2. Update record
    success = memory.update_record(calc_record.id, "User wants to master calculus and linear algebra.", "learning", 0.95)
    assert success
    
    updated_records = memory.recent_records()
    updated_calc = [r for r in updated_records if r.id == calc_record.id][0]
    assert updated_calc.fact == "User wants to master calculus and linear algebra."
    assert updated_calc.importance == 0.95
    
    # 3. Delete record
    del_success = memory.delete_record(pref_record.id)
    assert del_success
    
    post_delete_records = memory.recent_records()
    assert len(post_delete_records) == 1
    assert post_delete_records[0].id == calc_record.id

    # 4. Clear all
    memory.clear_all()
    assert len(memory.recent_records()) == 0
