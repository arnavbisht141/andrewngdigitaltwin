from __future__ import annotations

import sys
import os
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.chat import AndrewTwinChat
from memory.long_term import LongTermMemory
from rag.ingest import ingest
from rag.online_sources import ONLINE_SOURCES, fetch_online_sources
from rag.retrieval import HybridRetriever


st.set_page_config(page_title="Andrew Ng Digital Twin", page_icon="AI", layout="wide")

st.title("Andrew Ng Digital Twin")
st.caption("Educational emulation powered by persona prompting, RAG, Gemini, and persistent memory.")
st.caption(
    f"Gemini model: `{os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')}`. "
    "If Gemini hits quota, the app falls back to local RAG notes or an alternate LLM if configured."
)

if "chat" not in st.session_state:
    st.session_state.chat = AndrewTwinChat(
        retriever=HybridRetriever(),
        long_term_memory=LongTermMemory(),
    )
if "messages" not in st.session_state:
    st.session_state.messages = []

def render_sidebar() -> None:
    with st.sidebar:
        st.header("Memory")
        if st.button("Clear visible chat"):
            st.session_state.messages = []
            st.session_state.chat.short_term_memory.clear()
        st.divider()
        profile_tab, all_tab, corpus_tab = st.tabs(["Profile", "Memories", "Corpus"])

        with profile_tab:
            st.caption("Persistent profile inferred from explicit user statements.")
            profile = st.session_state.chat.long_term_memory.profile_summary()
            if profile:
                labels = {
                    "identity": "Identity",
                    "goal": "Goal",
                    "learning": "Learning",
                    "interest": "Interest",
                    "preference": "Preference",
                }
                for kind, label in labels.items():
                    if kind in profile:
                        st.markdown(f"**{label}**")
                        st.write(profile[kind])
            else:
                st.write("No profile memories yet.")

        with all_tab:
            st.caption("Long-term memories are stored in SQLite.")
            records = st.session_state.chat.long_term_memory.recent_records(limit=12)
            if records:
                for record in records:
                    st.markdown(f"**{record.kind.title()}** - importance `{record.importance:.2f}`")
                    st.write(record.fact)
            else:
                st.write("No long-term memories yet.")

        with corpus_tab:
            chunk_path = ROOT / "data" / "processed" / "chunks.jsonl"
            chunk_count = 0
            if chunk_path.exists():
                chunk_count = sum(1 for line in chunk_path.read_text(encoding="utf-8").splitlines() if line.strip())
            st.metric("Indexed chunks", chunk_count)
            st.caption(f"{len(ONLINE_SOURCES)} online Andrew Ng sources configured.")
            if st.button("Fetch online sources"):
                with st.spinner("Downloading online Andrew Ng sources..."):
                    written = fetch_online_sources()
                    count = ingest()
                    st.session_state.chat.retriever = HybridRetriever()
                st.success(f"Fetched {len(written)} sources and indexed {count} chunks.")
            if st.button("Rebuild RAG index"):
                count = ingest()
                st.session_state.chat.retriever = HybridRetriever()
                st.success(f"Indexed {count} chunks.")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

query = st.chat_input("Ask about machine learning, AI strategy, learning advice, or Andrew Ng's work")
if query:
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Retrieving sources and composing an Andrew Ng-style answer..."):
            result = st.session_state.chat.answer(query)
        st.markdown(result.answer)
        with st.expander("Retrieved sources"):
            if result.sources:
                for source in result.sources:
                    title = source.metadata.get("title", "Untitled")
                    source_name = source.metadata.get("source", "local corpus")
                    st.markdown(f"**{title}** - score `{source.score:.3f}`")
                    st.caption(source_name)
                    st.write(source.content[:700])
            else:
                st.write("No retrieved sources. Add `.txt` files to `data/raw/` and run `python -m rag.ingest`.")
        with st.expander("Relevant memories"):
            if result.memories:
                for memory in result.memories:
                    st.write(f"- {memory}")
            else:
                st.write("No relevant memories found.")

    st.session_state.messages.append({"role": "assistant", "content": result.answer})

render_sidebar()
