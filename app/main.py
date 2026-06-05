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

# Inject premium CSS styling
st.markdown(
    """
    <style>
    /* Import Premium Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');

    /* Apply typography to main layout text elements, leaving icon fonts untouched */
    html, body, p, li, label, input, select, textarea {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }

    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li,
    [data-testid="stMarkdownContainer"] span {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    /* Gradient text for titles and headers */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Outfit', sans-serif !important;
        font-weight: 600 !important;
        background: linear-gradient(135deg, #60EFFF 0%, #0072FF 100%);
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        margin-bottom: 0.2rem;
    }

    .stTitle {
        font-size: 2.8rem !important;
        font-weight: 700 !important;
        background: linear-gradient(135deg, #00C6FF 0%, #0072FF 100%);
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        margin-bottom: 0.5rem !important;
    }

    /* Premium custom scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    ::-webkit-scrollbar-track {
        background: rgba(0, 0, 0, 0.05);
        border-radius: 10px;
    }
    ::-webkit-scrollbar-thumb {
        background: rgba(0, 114, 255, 0.25);
        border-radius: 10px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(0, 114, 255, 0.5);
    }

    /* Glassmorphism card effect for expanders */
    div[data-testid="stExpander"] {
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
        background-color: rgba(255, 255, 255, 0.02) !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08) !important;
        margin-bottom: 1rem !important;
        transition: all 0.25s ease-in-out !important;
    }
    div[data-testid="stExpander"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 30px rgba(0, 114, 255, 0.12) !important;
        border-color: rgba(0, 114, 255, 0.3) !important;
    }

    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        border-right: 1px solid rgba(255, 255, 255, 0.08);
    }

    /* Force sidebar columns to stay side-by-side without wrapping vertically */
    section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important;
    }
    section[data-testid="stSidebar"] [data-testid="column"] {
        min-width: 0px !important;
    }
    
    /* Buttons custom transitions */
    div.stButton > button {
        border-radius: 10px !important;
        border: 1px solid rgba(0, 114, 255, 0.25) !important;
        font-weight: 500 !important;
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
    }
    div.stButton > button:hover {
        border-color: #0072FF !important;
        box-shadow: 0 4px 15px rgba(0, 114, 255, 0.25) !important;
        transform: translateY(-1px);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

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
        st.header("Memory & Settings")
        if st.button("Clear visible chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.chat.short_term_memory.clear()
        st.divider()
        profile_tab, all_tab, corpus_tab = st.tabs(["Profile", "Memories", "Corpus"])

        with profile_tab:
            st.caption("Customize your role and review inferred profile facts.")
            
            # Profession Selector
            professions = [
                "General Learner",
                "Student",
                "Software Engineer / Data Scientist",
                "Researcher / Scientist",
                "Business Executive / Product Manager"
            ]
            current_profile = st.session_state.chat.long_term_memory.profile_summary()
            current_prof_fact = current_profile.get("profession", "")
            
            default_index = 0
            for idx, prof in enumerate(professions):
                if prof.split(" / ")[0].lower() in current_prof_fact.lower():
                    default_index = idx
                    break
            
            selected_prof = st.selectbox("Select Your Role", options=professions, index=default_index)
            prof_key = selected_prof.split(" / ")[0]
            new_fact = f"User is a {prof_key}."
            if new_fact != current_prof_fact:
                st.session_state.chat.long_term_memory.add(new_fact, importance=1.0, kind="profession")
                st.toast(f"Role updated to {prof_key}!")
                st.rerun()
            
            st.divider()
            
            if current_profile:
                labels = {
                    "identity": "Identity",
                    "goal": "Goal",
                    "learning": "Learning",
                    "interest": "Interest",
                    "preference": "Preference",
                }
                for kind, label in labels.items():
                    if kind in current_profile:
                        st.markdown(f"**{label}**")
                        st.write(current_profile[kind])
            else:
                st.write("No other profile facts inferred yet.")

        with all_tab:
            st.caption("Manually manipulate long-term memories in SQLite.")
            
            # Add Memory manually
            with st.expander("➕ Add Memory Manually"):
                add_fact = st.text_input("Memory Fact (e.g. 'User likes Python')", key="add_fact_input")
                add_kind = st.selectbox("Category", ["general", "identity", "goal", "learning", "interest", "preference"], key="add_kind_select")
                add_imp = st.slider("Importance", 0.0, 1.0, 0.8, key="add_imp_slider")
                if st.button("Add Memory", key="add_mem_btn", use_container_width=True):
                    if add_fact.strip():
                        st.session_state.chat.long_term_memory.add(add_fact.strip(), importance=add_imp, kind=add_kind)
                        st.toast("Memory added!")
                        st.rerun()
                    else:
                        st.error("Fact text cannot be empty.")
            
            st.divider()
            
            # List memories with Edit and Delete
            records = st.session_state.chat.long_term_memory.recent_records(limit=100)
            if records:
                for record in records:
                    col1, col2, col3 = st.columns([7, 1.5, 1.5])
                    with col1:
                        st.markdown(f"**{record.kind.upper()}** (imp: `{record.importance:.2f}`)")
                        st.write(record.fact)
                    with col2:
                        # Edit Popover
                        with st.popover("✏️", help="Edit this memory"):
                            new_fact = st.text_input("Fact", value=record.fact, key=f"edit_fact_{record.id}")
                            new_kind = st.selectbox("Category", ["general", "identity", "goal", "learning", "interest", "preference", "profession"], index=["general", "identity", "goal", "learning", "interest", "preference", "profession"].index(record.kind), key=f"edit_kind_{record.id}")
                            new_imp = st.slider("Importance", 0.0, 1.0, value=record.importance, key=f"edit_imp_{record.id}")
                            if st.button("Save", key=f"edit_save_{record.id}", use_container_width=True):
                                st.session_state.chat.long_term_memory.update_record(record.id, new_fact, new_kind, new_imp)
                                st.toast("Memory updated!")
                                st.rerun()
                    with col3:
                        # Delete button
                        if st.button("🗑️", key=f"del_{record.id}", help="Delete this memory"):
                            st.session_state.chat.long_term_memory.delete_record(record.id)
                            st.toast("Memory deleted!")
                            st.rerun()
                    st.divider()
            else:
                st.write("No long-term memories stored yet.")

        with corpus_tab:
            chunk_path = ROOT / "data" / "processed" / "chunks.jsonl"
            chunk_count = 0
            if chunk_path.exists():
                chunk_count = sum(1 for line in chunk_path.read_text(encoding="utf-8").splitlines() if line.strip())
            st.metric("Indexed chunks", chunk_count)
            st.caption(f"{len(ONLINE_SOURCES)} online Andrew Ng sources configured.")
            if st.button("Fetch online sources", use_container_width=True):
                with st.spinner("Downloading online Andrew Ng sources..."):
                    written = fetch_online_sources()
                    count = ingest()
                    st.session_state.chat.retriever = HybridRetriever()
                st.success(f"Fetched {len(written)} sources and indexed {count} chunks.")
            if st.button("Rebuild RAG index", use_container_width=True):
                count = ingest()
                st.session_state.chat.retriever = HybridRetriever()
                st.success(f"Indexed {count} chunks.")

        st.divider()
        with st.expander("⚙️ Pipeline & RAG Settings"):
            top_k = st.slider("RAG Top K Chunks", min_value=1, max_value=10, value=st.session_state.get("top_k", 4))
            min_score = st.slider("RAG Min Score Threshold", min_value=0.0, max_value=1.0, value=st.session_state.get("min_score", 0.20), step=0.05)
            st.session_state.top_k = top_k
            st.session_state.min_score = min_score
            st.caption("Prune low-relevance sources to reduce prompt tokens and LLM API cost.")

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
            tk = st.session_state.get("top_k", 4)
            ms = st.session_state.get("min_score", 0.20)
            result = st.session_state.chat.answer(query, top_k=tk, min_score=ms)
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
