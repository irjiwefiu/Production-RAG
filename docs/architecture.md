# Architecture

## Runtime components

The root application is intentionally small and runs as two cooperating services:

- `streamlit_app.py`: browser UI, provider settings, PDF upload, and question form.
- `main.py`: FastAPI API for ingestion, retrieval, generation, and reset operations.
- `data_loader.py`: PDF extraction, chunking, and provider-specific embeddings.
- `vector_db.py`: Qdrant connection, collection lifecycle, upsert, and search.
- `custom_types.py`: shared Pydantic response models.

## Request flow

```text
Browser
  |
  v
Streamlit ---> POST /api/ingest ---> PDF loader ---> embeddings ---> Qdrant
  |
  +---------> POST /api/local-query-ai ---> Qdrant search ---> LLM answer
```

## Local storage

- `uploads/` contains temporary PDFs handled by the local service.
- `qdrant_storage/` is the embedded Qdrant fallback when `QDRANT_URL` is unavailable.
- Both are runtime data and are ignored by Git.
- A new Streamlit session calls `/api/reset`, which clears uploads and recreates the configured collection.

## Configuration

Copy `.env.example` to `.env` and provide only the keys needed by the selected providers. The Streamlit sidebar stores active UI settings in `st.session_state`; the FastAPI service continues to use environment configuration for provider selection.

## Development boundaries

Keep UI concerns in `streamlit_app.py`, API route concerns in `main.py`, embedding/chunking logic in `data_loader.py`, and vector-store concerns in `vector_db.py`. Changes that cross these boundaries should update the relevant documentation and tests.
