import os
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv, set_key

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
    st.sidebar.caption("You can input and save API keys here.")
    openai_key = st.sidebar.text_input(
        "OPENAI_API_KEY",
        value=os.getenv("OPENAI_API_KEY", ""),
        type="password",
        key="settings_openai_key",
    )
    gemini_key = st.sidebar.text_input(
        "GEMINI_API_KEY",
        value=os.getenv("GEMINI_API_KEY", ""),
        type="password",
        key="settings_gemini_key",
    )
    claude_key = st.sidebar.text_input(
        "ANTHROPIC_API_KEY",
        value=os.getenv("ANTHROPIC_API_KEY", ""),
        type="password",
        key="settings_claude_key",
    )
    ollama_key = st.sidebar.text_input(
        "OLLAMA_API_KEY",
        value=os.getenv("OLLAMA_API_KEY", ""),
        type="password",
        key="settings_ollama_key",
    )

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


def _fastapi_base_url() -> str:
    return os.getenv("FASTAPI_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def _post_backend_json(path: str, payload: dict, timeout: float = 120) -> dict:
    response = requests.post(f"{_fastapi_base_url()}{path}", json=payload, timeout=timeout)
    if response.status_code == 405:
        raise RuntimeError(
            "FASTAPI_BASE_URL points to the Streamlit service. Set it to the separate FastAPI Render service URL."
        )
    response.raise_for_status()
    return response.json()


def _upload_pdf_to_backend(path: Path) -> dict:
    with path.open("rb") as pdf_file:
        response = requests.post(
            f"{_fastapi_base_url()}/api/ingest",
            files={"file": (path.name, pdf_file, "application/pdf")},
            timeout=300,
        )
    if response.status_code == 405:
        raise RuntimeError(
            "FASTAPI_BASE_URL points to the Streamlit service. Set it to the separate FastAPI Render service URL."
        )
    response.raise_for_status()
    return response.json()


st.title("Upload a PDF to Ingest")
uploaded = st.file_uploader("Choose a PDF", type=["pdf"], accept_multiple_files=False)

if uploaded is not None:
    with st.spinner("Uploading and indexing PDF..."):
        path = save_uploaded_pdf(uploaded)
        st.session_state["last_uploaded_source"] = path.name
        try:
            result = _upload_pdf_to_backend(path)
            ingested = int(result.get("ingested", 0))
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
                output = _post_backend_json(
                    "/api/local-query-ai",
                    {"question": question.strip(), "top_k": int(top_k), "source_hint": source_hint},
                )
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

