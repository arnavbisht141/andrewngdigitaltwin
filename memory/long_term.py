from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "memory" / "andrew_twin_memory.sqlite"


@dataclass
class MemoryRecord:
    id: int
    fact: str
    kind: str
    importance: float
    created_at: str


class LongTermMemory:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fact TEXT NOT NULL UNIQUE,
                    kind TEXT NOT NULL DEFAULT 'general',
                    importance REAL NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(memories)").fetchall()
            }
            if "kind" not in columns:
                conn.execute("ALTER TABLE memories ADD COLUMN kind TEXT NOT NULL DEFAULT 'general'")

    def add(self, fact: str, importance: float = 0.75, kind: str = "general") -> None:
        fact = fact.strip()
        if not fact:
            return
        with self._connect() as conn:
            if kind in ("profession", "identity"):
                conn.execute("DELETE FROM memories WHERE kind = ?", (kind,))
            conn.execute(
                """
                INSERT INTO memories(fact, kind, importance, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(fact) DO UPDATE SET
                    kind = excluded.kind,
                    importance = max(memories.importance, excluded.importance),
                    created_at = excluded.created_at
                """,
                (fact, kind, importance, datetime.now(timezone.utc).isoformat()),
            )

    def learn_from_turn(self, user_text: str, assistant_text: str) -> None:
        del assistant_text
        extraction_rules = [
            (r"\bmy name is\s+([A-Z][A-Za-z .'-]{1,60})", "identity", "User's name is {value}.", 1.0),
            (r"\bcall me\s+([A-Z][A-Za-z .'-]{1,60})", "identity", "User prefers to be called {value}.", 1.0),
            (r"\bI(?:'m| am)\s+([A-Z][A-Za-z .'-]{1,60})\b", "identity", "User's name is {value}.", 0.95),
            (r"\bI am learning ([^.?!]+)", "learning", "User is learning {value}.", 0.9),
            (r"\bI'm learning ([^.?!]+)", "learning", "User is learning {value}.", 0.9),
            (r"\bI want to learn ([^.?!]+)", "learning", "User wants to learn {value}.", 0.9),
            (r"\bmy goal is ([^.?!]+)", "goal", "User's goal is {value}.", 0.95),
            (r"\bI am interested in ([^.?!]+)", "interest", "User is interested in {value}.", 0.85),
            (r"\bI prefer ([^.?!]+)", "preference", "User prefers {value}.", 0.85),
            (r"\bremember that ([^.?!]+)", "general", "User asked me to remember: {value}.", 0.9),
        ]
        for pattern, kind, template, importance in extraction_rules:
            match = re.search(pattern, user_text, flags=re.IGNORECASE)
            if match:
                value = self._clean_value(match.group(1))
                if value:
                    self.add(template.format(value=value), importance=importance, kind=kind)

    def search(self, query: str, limit: int = 5) -> list[str]:
        terms = {term.lower() for term in re.findall(r"[a-zA-Z0-9]+", query)}
        memories = self.recent(limit=100)
        ranked = []
        for memory in memories:
            memory_terms = {term.lower() for term in re.findall(r"[a-zA-Z0-9]+", memory)}
            score = len(terms & memory_terms)
            if score:
                ranked.append((score, memory))
        ranked.sort(reverse=True)
        return [memory for _, memory in ranked[:limit]]

    def recent(self, limit: int = 10) -> list[str]:
        return [record.fact for record in self.recent_records(limit=limit)]

    def recent_records(self, limit: int = 10, kind: str | None = None) -> list[MemoryRecord]:
        with self._connect() as conn:
            if kind:
                rows = conn.execute(
                    """
                    SELECT id, fact, kind, importance, created_at
                    FROM memories
                    WHERE kind = ?
                    ORDER BY importance DESC, created_at DESC
                    LIMIT ?
                    """,
                    (kind, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, fact, kind, importance, created_at
                    FROM memories
                    ORDER BY importance DESC, created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [
            MemoryRecord(id=row[0], fact=row[1], kind=row[2], importance=row[3], created_at=row[4])
            for row in rows
        ]

    def profile_summary(self) -> dict[str, str]:
        summary: dict[str, str] = {}
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT kind, fact
                FROM memories
                WHERE kind IN ('identity', 'goal', 'learning', 'interest', 'preference', 'profession')
                ORDER BY importance DESC, created_at DESC
                """
            ).fetchall()
        for kind, fact in rows:
            summary.setdefault(kind, fact)
        return summary

    def delete_record(self, record_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM memories WHERE id = ?", (record_id,))
            return cursor.rowcount > 0

    def update_record(self, record_id: int, fact: str, kind: str, importance: float) -> bool:
        fact = fact.strip()
        if not fact:
            return False
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE memories
                SET fact = ?, kind = ?, importance = ?, created_at = ?
                WHERE id = ?
                """,
                (fact, kind, importance, datetime.now(timezone.utc).isoformat(), record_id),
            )
            return cursor.rowcount > 0

    def add_manual_record(self, fact: str, kind: str, importance: float = 0.8) -> None:
        self.add(fact=fact, importance=importance, kind=kind)

    def clear_all(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM memories")

    @staticmethod
    def _clean_value(value: str) -> str:
        value = re.sub(r"\s+", " ", value).strip(" .,!?:;")
        value = re.split(r"\s+(?:and|but)\s+I\s+", value, maxsplit=1, flags=re.IGNORECASE)[0]
        value = re.sub(r"\b(and|but|also)$", "", value, flags=re.IGNORECASE).strip()
        return value
