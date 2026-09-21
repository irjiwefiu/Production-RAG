import os
from pathlib import Path
import uuid

import requests
import streamlit as st
from dotenv import load_dotenv, set_key
from data_loader import embed_texts, load_and_chunk_pdf
from main import _context_prompt, _search_contexts, generate_answer
from vector_db import get_qdrant_storage

load_dotenv()
ENV_FILE = Path(".env").resolve()

st.set_page_config(page_title="RAG Ingest PDF", page_icon="📄", layout="centered")

if os.getenv("OLLAMA_API_KEY"):
    os.environ.setdefault("LLM_PROVIDER", "ollama")
    os.environ.setdefault("EMBED_PROVIDER", "ollama")
    os.environ.setdefault("OLLAMA_BASE_URL", "https://api.ollama.com")


def _save_env(key: str, value: str) -> None:
    os.environ[key] = value
    set_key(str(ENV_FILE), key, value)


def _llm_model_key(provider: str) -> str:
    return {
        "openai": "OPENAI_MODEL",
        "gemini": "GEMINI_MODEL",
        "claude": "CLAUDE_MODEL",
        "ollama": "OLLAMA_MODEL",
        "local": "LOCAL_MODEL",
    }.get(provider, "OPENAI_MODEL")


def _embed_model_key(provider: str) -> str:
    return {
        "openai": "EMBED_MODEL",
        "gemini": "GEMINI_EMBED_MODEL",
        "ollama": "OLLAMA_EMBED_MODEL",
        "local": "LOCAL_EMBED_MODEL",
    }.get(provider, "EMBED_MODEL")


def _ollama_headers() -> dict[str, str]:
    api_key = os.getenv("OLLAMA_API_KEY")
    if not api_key:
        return {}
    return {"Authorization": f"Bearer {api_key}"}


def _fetch_ollama_models() -> list[str]:
    base_url = os.getenv("OLLAMA_BASE_URL", "https://api.ollama.com")
    try:
        response = requests.get(
            f"{base_url}/api/tags",
            headers=_ollama_headers(),
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        models = [m.get("name", "") for m in payload.get("models", [])]
        models = [m for m in models if m]
        if models:
            return sorted(set(models))
    except Exception:
        pass
    return ["gemma3:4b", "gpt-oss:20b", "llama3.1"]


def _llm_models_for(provider: str) -> list[str]:
    if provider == "openai":
        return ["gpt-4o-mini", "gpt-4.1-mini", "gpt-4.1", "o3-mini"]
    if provider == "gemini":
        return ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-flash-latest"]
    if provider == "claude":
        return ["claude-3-5-haiku-latest", "claude-3-5-sonnet-latest", "claude-3-7-sonnet-latest"]
    if provider == "ollama":
        return _fetch_ollama_models()
    return ["local-default"]


def _embed_models_for(provider: str) -> list[str]:
    if provider == "openai":
        return ["text-embedding-3-small", "text-embedding-3-large"]
    if provider == "gemini":
        return ["gemini-embedding-001"]
    if provider == "ollama":
        models = _fetch_ollama_models()
        if "nomic-embed-text" not in models:
            models = ["nomic-embed-text", *models]
        return models
    return ["local-hash-v1"]


def _current_provider(value: str, allowed: list[str], default: str) -> str:
    if value in allowed:
        return value
    return default


def _secret_input(label: str, key: str) -> str:
    return st.sidebar.text_input(
        label,
        value="",
        placeholder="Enter a new key to replace the current one",
        type="password",
        key=key,
        help="The existing key is kept hidden. Leave this blank to keep it unchanged.",
    )


def _render_model_settings() -> None:
    llm_options = ["openai", "gemini", "claude", "ollama", "local"]
    embed_options = ["openai", "gemini", "ollama", "local"]

    current_llm = _current_provider(os.getenv("LLM_PROVIDER", "ollama").lower(), llm_options, "ollama")
    current_embed = _current_provider(os.getenv("EMBED_PROVIDER", "ollama").lower(), embed_options, "ollama")

    st.sidebar.header("Model Settings")
    llm_provider = st.sidebar.selectbox(
        "LLM provider",
        llm_options,
        index=llm_options.index(current_llm),
        key="settings_llm_provider",
    )
    llm_model_key = _llm_model_key(llm_provider)
    llm_models = _llm_models_for(llm_provider)
    current_llm_model = os.getenv(llm_model_key, llm_models[0] if llm_models else "")
    llm_model_default = current_llm_model if current_llm_model in llm_models else llm_models[0]
    llm_model = st.sidebar.selectbox(
        "LLM model version",
        llm_models,
        index=llm_models.index(llm_model_default),
        key="settings_llm_model",
    )

    embed_provider = st.sidebar.selectbox(
        "Embedding provider",
        embed_options,
        index=embed_options.index(current_embed),
        key="settings_embed_provider",
    )
    embed_model_key = _embed_model_key(embed_provider)
    embed_models = _embed_models_for(embed_provider)
    current_embed_model = os.getenv(embed_model_key, embed_models[0] if embed_models else "")
    embed_model_default = current_embed_model if current_embed_model in embed_models else embed_models[0]
    embed_model = st.sidebar.selectbox(
        "Embedding model version",
        embed_models,
        index=embed_models.index(embed_model_default),
        key="settings_embed_model",
    )

    embed_dim = 768 if embed_provider in {"gemini", "ollama", "local"} else 3072
    st.sidebar.caption(f"Embedding dimension: {embed_dim} (auto)")

    st.sidebar.markdown("API Key Source")
    st.sidebar.caption("Enter a new key only when replacing the current deployment secret.")
    key_version = st.session_state.get("api_key_input_version", 0)
    openai_key = _secret_input("OPENAI_API_KEY", f"settings_openai_key_{key_version}")
    gemini_key = _secret_input("GEMINI_API_KEY", f"settings_gemini_key_{key_version}")
    claude_key = _secret_input("ANTHROPIC_API_KEY", f"settings_claude_key_{key_version}")
    ollama_key = _secret_input("OLLAMA_API_KEY", f"settings_ollama_key_{key_version}")

    save = st.sidebar.button("Save settings", key="settings_save")

    if save:
        _save_env("LLM_PROVIDER", llm_provider)
        _save_env(llm_model_key, llm_model)
        _save_env("EMBED_PROVIDER", embed_provider)
        _save_env(embed_model_key, embed_model)
        _save_env("EMBED_DIM", str(int(embed_dim)))

        if openai_key:
            _save_env("OPENAI_API_KEY", openai_key)
        if gemini_key:
            _save_env("GEMINI_API_KEY", gemini_key)
        if claude_key:
            _save_env("ANTHROPIC_API_KEY", claude_key)
        if ollama_key:
            _save_env("OLLAMA_API_KEY", ollama_key)

        st.session_state["api_key_input_version"] = key_version + 1
        st.sidebar.success("Settings saved. Applying now...")
        st.rerun()


_render_model_settings()

def save_uploaded_pdf(file) -> Path:
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)
    file_path = uploads_dir / file.name
    file_bytes = file.getbuffer()
    file_path.write_bytes(file_bytes)
    return file_path


def _source_hint() -> str | None:
    hint = st.session_state.get("last_uploaded_source")
    if isinstance(hint, str) and hint.strip():
        return hint.strip()
    return None


def _ingest_pdf_locally(path: Path) -> int:
    chunks = load_and_chunk_pdf(str(path.resolve()))
    vectors = embed_texts(chunks)
    source_id = path.name
    ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source_id}:{i}")) for i in range(len(chunks))]
    payloads = [{"source": source_id, "text": chunks[i]} for i in range(len(chunks))]
    get_qdrant_storage().upsert(ids, vectors, payloads)
    return len(chunks)


def _query_locally(question: str, top_k: int, source_hint: str | None = None) -> dict:
    found = _search_contexts(question, top_k, source_hint)
    contexts = found.get("contexts", [])
    answer = generate_answer(_context_prompt(question, contexts))
    return {
        "answer": answer,
        "sources": found.get("sources", []),
        "num_contexts": len(contexts),
    }


st.title("Upload a PDF to Ingest")
uploaded = st.file_uploader("Choose a PDF", type=["pdf"], accept_multiple_files=False)

if uploaded is not None:
    with st.spinner("Uploading and indexing PDF..."):
        path = save_uploaded_pdf(uploaded)
        st.session_state["last_uploaded_source"] = path.name
        try:
            ingested = _ingest_pdf_locally(path)
            st.success(f"Ingested {ingested} chunks and uploaded them to Qdrant: {path.name}")
            st.caption("You can upload another PDF if you like.")
        except Exception as exc:
            st.error(f"Ingestion failed: {exc}")

st.divider()
st.title("Ask a question about your PDFs")

with st.form("rag_query_form"):
    question = st.text_input("Your question")
    top_k = st.number_input("How many chunks to retrieve", min_value=1, max_value=20, value=5, step=1)
    submitted = st.form_submit_button("Ask")

    if submitted and question.strip():
        with st.spinner("Searching documents and generating answer..."):
            source_hint = _source_hint()
            try:
                output = _query_locally(question.strip(), int(top_k), source_hint)
                answer = output.get("answer", "")
                sources = output.get("sources", [])

                st.subheader("Answer")
                st.write(answer or "(No answer)")
                if sources:
                    st.caption("Sources")
                    for s in sources:
                        st.write(f"- {s}")
            except Exception as exc:
                st.error(f"Query failed: {exc}")

