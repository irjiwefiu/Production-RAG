import os
import shutil
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title="RAG Ingest PDF", page_icon="📄", layout="centered")

def render_sidebar() -> dict[str, str | dict[str, str]]:
    providers = {
        "OpenAI": "openai",
        "Anthropic": "claude",
        "Google Gemini": "gemini",
        "Ollama": "ollama",
        "Groq": "groq",
    }
    models_by_provider = {
        "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini"],
        "claude": ["claude-3-5-sonnet-20240620", "claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"],
        "gemini": ["gemini-3.6-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
        "ollama": ["llama3.1", "llama3.2", "mistral"],
        "groq": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
    }
    api_key_env_by_provider = {
        "openai": "OPENAI_API_KEY",
        "claude": "ANTHROPIC_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "ollama": "OLLAMA_API_KEY",
        "groq": "GROQ_API_KEY",
    }
    embedding_models = [
        "text-embedding-3-small",
        "text-embedding-3-large",
        "bge-small-en-v1.5",
        "gemini-embedding-001",
        "ollama/nomic-embed-text",
    ]

    st.sidebar.header("Configuration")
    mode = st.sidebar.radio(
        "Configuration mode",
        ["Default (Environment Variables)", "Custom API Key"],
        key="configuration_mode",
    )
    use_environment = mode == "Default (Environment Variables)"

    provider_label = st.sidebar.selectbox(
        "Provider",
        list(providers),
        format_func=lambda label: label,
        key="selected_provider_label",
    )
    provider = providers[provider_label]

    configured_model = os.getenv(
        {"openai": "OPENAI_MODEL", "claude": "CLAUDE_MODEL", "gemini": "GEMINI_MODEL", "ollama": "OLLAMA_MODEL"}.get(provider, ""),
        "",
    )
    model_options = list(models_by_provider[provider])
    if configured_model and configured_model not in model_options:
        model_options.insert(0, configured_model)
    if st.session_state.get("selected_llm_model") not in model_options:
        st.session_state["selected_llm_model"] = configured_model or model_options[0]
    selected_model = st.sidebar.selectbox("LLM model", model_options, key="selected_llm_model")

    configured_embedding = os.getenv("EMBED_MODEL", "")
    embedding_options = list(embedding_models)
    if configured_embedding and configured_embedding not in embedding_options:
        embedding_options.insert(0, configured_embedding)
    selected_embedding = st.sidebar.selectbox(
        "Embedding model",
        embedding_options,
        key="selected_embedding_model",
    )

    api_key_env = api_key_env_by_provider[provider]
    saved_keys = st.session_state.setdefault("provider_api_keys", {})
    input_key = f"api_key_input_{provider}"
    previous_mode = st.session_state.get("previous_configuration_mode")
    if use_environment:
        st.session_state[input_key] = os.getenv(api_key_env, "")
    elif previous_mode != mode or input_key not in st.session_state:
        st.session_state[input_key] = str(saved_keys.get(provider) or "")
    st.session_state["previous_configuration_mode"] = mode
    st.sidebar.markdown(
        """
        <style>
        section[data-testid="stSidebar"] [data-testid="stTextInput"] button {
            display: none;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    api_key = st.sidebar.text_input(
        f"{provider_label} API key",
        type="password",
        key=input_key,
        disabled=use_environment,
        help=f"Uses {api_key_env} when Default mode is selected.",
    ).strip()

    current_config: dict[str, str | dict[str, str]] = {
        "provider": provider,
        "model": selected_model,
        "embedding_model": selected_embedding,
        "api_key": api_key,
        "api_keys": {provider: api_key},
        "configuration_mode": "environment" if use_environment else "custom",
    }
    if st.sidebar.button("Save Settings", type="primary"):
        if provider not in {"ollama"} and not api_key:
            st.sidebar.error(f"Enter an API key for {provider_label} before saving.")
        else:
            saved_keys[provider] = api_key
            st.session_state["active_config"] = current_config
            st.session_state["session_gemini_api_key"] = api_key if provider == "gemini" else ""
            st.sidebar.success("Settings saved successfully!")

    return st.session_state.get("active_config", current_config)


def _gemini_headers() -> dict[str, str]:
    api_key = st.session_state.get("session_gemini_api_key", "").strip()
    return {"X-Gemini-Api-Key": api_key} if api_key else {}


def _clear_local_uploads() -> None:
    uploads_dir = Path("uploads")
    if not uploads_dir.exists():
        return
    for child in uploads_dir.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def _reset_on_new_session() -> None:
    if st.session_state.get("session_initialized"):
        return
    _clear_local_uploads()
    try:
        response = requests.post(f"{_fastapi_base_url()}/api/reset", timeout=120)
    except requests.exceptions.RequestException as exc:
        st.sidebar.warning(
            "FastAPI reset was unavailable. Start it with `python -m uvicorn main:app --reload` "
            f"before uploading or asking questions. ({exc.__class__.__name__})"
        )
        st.session_state["session_initialized"] = True
        return
    response.raise_for_status()
    st.session_state["session_initialized"] = True


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


render_sidebar()
_reset_on_new_session()


def _post_backend_json(path: str, payload: dict, timeout: float = 120) -> dict:
    response = requests.post(
        f"{_fastapi_base_url()}{path}",
        json=payload,
        headers=_gemini_headers(),
        timeout=timeout,
    )
    if response.status_code == 405:
        raise RuntimeError(
            "FASTAPI_BASE_URL points to the Streamlit service. Set it to the separate FastAPI Render service URL."
        )
    if response.status_code == 429:
        try:
            detail = response.json().get("detail")
        except ValueError:
            detail = None
        raise RuntimeError(detail or "The AI provider quota is exhausted. Please try again later.")
    response.raise_for_status()
    return response.json()


def _upload_pdf_to_backend(path: Path) -> dict:
    with path.open("rb") as pdf_file:
        response = requests.post(
            f"{_fastapi_base_url()}/api/ingest",
            files={"file": (path.name, pdf_file, "application/pdf")},
            headers=_gemini_headers(),
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

