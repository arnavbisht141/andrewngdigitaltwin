from __future__ import annotations

import os
import hashlib
import re
import sqlite3
import time
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    import google.generativeai as genai
except ImportError:  # pragma: no cover - exercised only without dependency
    genai = None

try:
    import openai
except ImportError:  # pragma: no cover
    openai = None

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

from memory.long_term import LongTermMemory
from memory.short_term import ShortTermMemory
from persona.prompt_builder import build_prompt
from rag.retrieval import HybridRetriever, RetrievalResult, tokenize

ROOT = Path(__file__).resolve().parents[1]
if load_dotenv is not None:
    load_dotenv(ROOT / ".env")

CACHE_PATH = ROOT / "memory" / "response_cache.sqlite"


@dataclass
class ChatResult:
    answer: str
    sources: list[RetrievalResult]
    memories: list[str]


class AndrewTwinChat:
    def __init__(
        self,
        retriever: HybridRetriever | None = None,
        long_term_memory: LongTermMemory | None = None,
        short_term_memory: ShortTermMemory | None = None,
        model_name: str | None = None,
    ) -> None:
        self.retriever = retriever or HybridRetriever()
        self.long_term_memory = long_term_memory or LongTermMemory()
        self.short_term_memory = short_term_memory or ShortTermMemory(max_messages=15)
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        raw_keys = [key.strip() for key in os.getenv("GEMINI_API_KEYS", "").split(",") if key.strip()]
        if not raw_keys:
            idx = 1
            while True:
                numbered_key = os.getenv(f"GEMINI_API_KEY{idx}")
                if numbered_key:
                    raw_keys.append(numbered_key.strip())
                    idx += 1
                else:
                    break
        if not raw_keys:
            default_key = os.getenv("GEMINI_API_KEY")
            raw_keys = [default_key] if default_key else []
        self.gemini_api_keys = raw_keys
        self.gemini_key_index = 0
        self.gemini_cooldown_until = 0.0
        self.last_gemini_request = 0.0
        self._init_cache()

    def answer(self, user_text: str, top_k: int = 4, min_score: float = 0.2) -> ChatResult:
        sources = self.retriever.search(user_text, top_k=top_k, min_score=min_score)
        memories = self.long_term_memory.search(user_text, limit=5)
        
        # Determine target audience role from long-term profile
        profile = self.long_term_memory.profile_summary()
        user_role = None
        if "profession" in profile:
            prof_text = profile["profession"]
            for role_keyword in ["Student", "Scientist", "Researcher", "Engineer", "Developer", "Executive", "Manager"]:
                if role_keyword.lower() in prof_text.lower():
                    user_role = role_keyword
                    break
            if not user_role:
                user_role = prof_text

        local_answer = self._local_memory_ack(user_text)
        if local_answer:
            self.short_term_memory.add("user", user_text)
            self.short_term_memory.add("assistant", local_answer)
            return ChatResult(answer=local_answer, sources=sources, memories=self.long_term_memory.recent(limit=5))

        prompt = build_prompt(
            user_query=user_text,
            conversation_history=self.short_term_memory.messages,
            retrieved_chunks=sources,
            memories=memories,
            user_role=user_role,
        )
        answer = self._cached_generate(prompt, sources)
        self.short_term_memory.add("user", user_text)
        self.short_term_memory.add("assistant", answer)
        self.long_term_memory.learn_from_turn(user_text, answer)
        return ChatResult(answer=answer, sources=sources, memories=memories)

    def _cached_generate(self, prompt: str, sources: Iterable[RetrievalResult]) -> str:
        key = hashlib.sha256(f"{self.model_name}\n{prompt}".encode("utf-8")).hexdigest()
        cached = self._cache_get(key)
        if cached:
            return cached
        answer = self._generate(prompt, sources)
        if not self._is_transient_error_message(answer):
            self._cache_set(key, answer)
        return answer

    def _generate(self, prompt: str, sources: Iterable[RetrievalResult]) -> str:
        if genai is None or not self.gemini_api_keys:
            return self._offline_response(prompt, sources)
        if time.time() < self.gemini_cooldown_until:
            return self._rate_limit_fallback(sources)
        # Configure retry behaviour via environment for flexibility
        max_retries = int(os.getenv("GEMINI_MAX_RETRIES", "3"))
        backoff_base = float(os.getenv("GEMINI_BACKOFF_BASE", "1.5"))

        # simple per-instance throttle to avoid rapid-fire requests
        min_interval = float(os.getenv("GEMINI_MIN_INTERVAL_SECONDS", "0.8"))
        if time.time() - self.last_gemini_request < min_interval:
            return self._synthesise_offline_answer(sources)

        text = ""
        for attempt in range(1, max_retries + 1):
            api_key = self._choose_gemini_key()
            genai.configure(api_key=api_key)
            try:
                model = genai.GenerativeModel(self.model_name)
                response = model.generate_content(prompt)
                text = (response.text or "").strip()
                self.last_gemini_request = time.time()
                break
            except Exception as exc:
                if self._looks_like_rate_limit(exc):
                    retry_after = self._parse_retry_after(exc)
                    if retry_after is None:
                        sleep_time = (backoff_base ** attempt) + random.uniform(0, 1)
                    else:
                        sleep_time = retry_after

                    if attempt < max_retries:
                        time.sleep(sleep_time)
                        continue
                    self.gemini_cooldown_until = time.time() + int(
                        os.getenv("GEMINI_RATE_LIMIT_COOLDOWN_SECONDS", "75")
                    )
                    alternate = self._alternate_llm_available()
                    if alternate:
                        return self._generate_with_alternate(prompt, sources)
                    return self._rate_limit_fallback(sources)
                return (
                    "I found your Gemini configuration, but the Gemini request failed. "
                    f"Please check the API key, model name, and network access. Error: {exc}"
                )

        return text or "Gemini returned an empty response. Please try again with a more specific question."

    def _choose_gemini_key(self) -> str:
        if not self.gemini_api_keys:
            return ""
        key = self.gemini_api_keys[self.gemini_key_index]
        self.gemini_key_index = (self.gemini_key_index + 1) % len(self.gemini_api_keys)
        return key

    def _synthesise_offline_answer(self, sources: Iterable[RetrievalResult]) -> str:
        """Produce a concise synthesized answer from retrieved chunks as a better offline fallback."""
        source_list = list(sources)[:6]
        query_terms = set()
        if hasattr(self, 'short_term_memory') and self.short_term_memory.messages:
            query_terms = set(tokenize(self.short_term_memory.messages[-1]['content']))

        if not source_list:
            return self._offline_response("", sources)

        summaries = []
        for idx, item in enumerate(source_list, start=1):
            content = item.content.strip()
            title = item.metadata.get("title") or item.metadata.get("source") or f"Source {idx}"
            sentences = re.split(r"(?<=[.!?])\s+", content)
            scored = []
            for sentence in sentences:
                tokens = tokenize(sentence)
                if len(tokens) < 8:
                    continue
                overlap = sum(1 for token in tokens if token in query_terms)
                scored.append((overlap, len(tokens), sentence.strip()))
            scored.sort(key=lambda item: (item[0], -item[1]), reverse=True)
            extract = scored[0][2] if scored and scored[0][0] > 0 else sentences[0] if sentences else ""
            if extract:
                summaries.append(f"[{idx}] {title}: {extract}")

        if not summaries:
            return self._offline_response("", sources)

        body = "\n\n".join(summaries[:4])
        source_names = ", ".join(
            item.metadata.get("title", f"Source {idx}") for idx, item in enumerate(source_list[:4], start=1)
        )
        return (
            "(Fallback) Gemini is unavailable, so I'm answering from the most relevant retrieved Andrew Ng and related sources. "
            "This response is based directly on those documents.\n\n"
            f"{body}\n\nSources: {source_names}"
        )

    def _alternate_llm_available(self) -> bool:
        provider = os.getenv("FALLBACK_LLM_PROVIDER", "OPENAI").upper()
        if provider == "OPENAI" and openai is not None and os.getenv("OPENAI_API_KEY"):
            return True
        return False

    def _generate_with_alternate(self, prompt: str, sources: Iterable[RetrievalResult]) -> str:
        provider = os.getenv("FALLBACK_LLM_PROVIDER", "OPENAI").upper()
        if provider == "OPENAI" and openai is not None and os.getenv("OPENAI_API_KEY"):
            return self._openai_generate(prompt)
        return self._offline_response(prompt, sources)

    def _openai_generate(self, prompt: str) -> str:
        api_key = os.getenv("OPENAI_API_KEY")
        model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        if not api_key:
            return "OpenAI fallback is not configured. Please set OPENAI_API_KEY."
        openai.api_key = api_key
        try:
            response = openai.ChatCompletion.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512,
                temperature=0.7,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            return (
                "OpenAI fallback is configured, but the request failed. "
                f"Error: {exc}"
            )

    @staticmethod
    def _parse_retry_after(exc: Exception) -> int | None:
        """Try to extract a numeric retry-after value (seconds) from an exception message."""
        text = str(exc).lower()
        m = re.search(r"retry-after[:=]\s*(\d+)", text)
        if not m:
            m = re.search(r"retry_after[:=]\s*(\d+)", text)
        if not m:
            m = re.search(r"(\d+)\s*seconds", text)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                return None
        return None

    def _local_memory_ack(self, user_text: str) -> str | None:
        memory_only = (
            len(user_text) <= 180
            and "?" not in user_text
            and re.search(
                r"\b(my name is|call me|remember that|my goal is|i prefer|i am learning|i'm learning|i want to learn)\b",
                user_text,
                flags=re.IGNORECASE,
            )
        )
        if not memory_only:
            return None
        self.long_term_memory.learn_from_turn(user_text, "")
        profile = self.long_term_memory.profile_summary()
        if "identity" in profile:
            return f"I'll remember that. {profile['identity']}"
        if "goal" in profile:
            return f"I'll keep that goal in mind. {profile['goal']}"
        if "learning" in profile:
            return f"I'll remember that for future examples. {profile['learning']}"
        if "preference" in profile:
            return f"Got it. {profile['preference']}"
        return "I'll remember that for future turns."

    @staticmethod
    def _looks_like_rate_limit(exc: Exception) -> bool:
        text = str(exc).lower()
        return any(marker in text for marker in ("429", "quota", "rate limit", "resource_exhausted"))

    @staticmethod
    def _is_transient_error_message(answer: str) -> bool:
        return (
            "Gemini is rate-limited" in answer
            or "Gemini request failed" in answer
            or "Gemini returned an empty response" in answer
        )

    def _rate_limit_fallback(self, sources: Iterable[RetrievalResult]) -> str:
        return (
            "Gemini is rate-limited right now, so I am switching to a local RAG fallback. "
            + self._offline_response("", sources)
        )

    def _init_cache(self) -> None:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(CACHE_PATH) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS response_cache (
                    cache_key TEXT PRIMARY KEY,
                    answer TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )

    @staticmethod
    def _cache_get(cache_key: str) -> str | None:
        with sqlite3.connect(CACHE_PATH) as conn:
            row = conn.execute("SELECT answer FROM response_cache WHERE cache_key = ?", (cache_key,)).fetchone()
        return row[0] if row else None

    @staticmethod
    def _cache_set(cache_key: str, answer: str) -> None:
        with sqlite3.connect(CACHE_PATH) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO response_cache(cache_key, answer, created_at) VALUES (?, ?, ?)",
                (cache_key, answer, time.time()),
            )

    @staticmethod
    def _offline_response(prompt: str, sources: Iterable[RetrievalResult]) -> str:
        source_list = list(sources)
        if not source_list:
            return (
                "I would approach this by first building intuition, then adding the technical details. "
                "I do not have retrieved Andrew Ng source material for this exact question yet, so I "
                "would be careful not to overstate a claim. Add more corpus files and configure "
                "GEMINI_API_KEY for a fully grounded response."
            )

        titles = ", ".join({item.metadata.get("title", "source") for item in source_list[:3]})
        source_notes = "\n".join(
            f"- {item.metadata.get('title', 'Source')}: {item.content[:260].strip()}..."
            for item in source_list[:3]
        )
        return (
            "Let me explain this in a simple, practical way. Based on the retrieved material "
            f"from {titles}, the key idea is to start with the intuition, connect it to an "
            "engineering use case, and then decide what evidence would validate the solution.\n\n"
            f"Relevant retrieved notes:\n{source_notes}"
        )
