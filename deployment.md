# Render Deployment Guide

This guide deploys the current root application to Render using Gemini and Qdrant Cloud.

## Recommended Render setup

Use one Render Web Service running Streamlit. The app performs ingestion and querying directly in the Streamlit process:

- Streamlit processes the PDF and creates embeddings.
- Vectors are persisted in Qdrant Cloud.

## 1. Create the Render service

1. Push this repository to GitHub.
2. In Render, choose **New > Web Service**.
3. Connect the repository and select the `feature/remote-qdrant` branch, or deploy your merged production branch.
4. Use these settings:

| Setting | Value |
| --- | --- |
| Runtime | Python 3 |
| Build command | `pip install .` |
| Start command | `streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port $PORT --server.headless true` |
| Health check path | `/` |
| Instance type | Free for testing, paid for production |

Render provides the `$PORT` environment variable. The app must bind to `0.0.0.0`, not `127.0.0.1`.

## 2. Configure Render environment variables

Add these in the Render service under **Environment > Environment Variables**. Never commit these values to GitHub.

```text
LLM_PROVIDER=gemini
GEMINI_MODEL=gemini-3.6-flash
GEMINI_API_KEY=<your-gemini-api-key>

EMBED_PROVIDER=gemini
GEMINI_EMBED_MODEL=gemini-embedding-001
EMBED_DIM=768

QDRANT_URL=https://<your-qdrant-cluster>.cloud.qdrant.io
QDRANT_API_KEY=<your-qdrant-api-key>
QDRANT_COLLECTION=docs

```

Optional settings:

```text
QDRANT_PATH=/tmp/qdrant_storage
UPLOADS_DIR=/tmp/uploads
```

`QDRANT_PATH` is only a fallback. Render's local filesystem is temporary, so Qdrant Cloud must be the real persistent store.

## 3. Deploy and test

After creating the service:

1. Wait for the build to complete.
2. Open the Render URL.
3. Upload a small PDF.
4. Wait for the message confirming that chunks were uploaded to Qdrant.
5. Ask a question using wording that appears in the PDF.

The first request can be slow on a cold Render instance. The Gemini embedding dimension must remain `768`, matching the `docs` Qdrant collection.

## 4. Qdrant checks

The Qdrant Cloud cluster must contain a collection named `docs` with:

- Distance: `Cosine`
- Vector size: `768`

If the collection was created with a different embedding dimension, create a new collection or re-index all documents after changing the embedding model. Do not mix vectors from different embedding models in one collection.

## 5. Gemini API notes

The Gemini API may provide a free tier with rate limits. It is not unlimited. Configure billing and monitor quotas before using the service for real users.

The application currently uses:

- `gemini-3.6-flash` for answer generation
- `gemini-embedding-001` for document and query embeddings

Keep the Gemini and Qdrant keys in Render's encrypted environment settings. Do not put them in Streamlit UI code, GitHub, or committed `.env` files.

## 6. Common Render problems

### Application failed to bind to a port

Use exactly:

```text
streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port $PORT --server.headless true
```

### Qdrant connection fails

Check that `QDRANT_URL` has no trailing path, `QDRANT_API_KEY` is valid, and the Qdrant cluster is running. Never expose the API key in logs or screenshots.

### Answers say no relevant context

Check the ingestion success message and verify that the Qdrant collection contains points. Re-upload the PDF after changing `EMBED_DIM` or the embedding model.

### Uploads disappear after restart

Render's local disk is ephemeral. The vectors remain in Qdrant Cloud, but uploaded source files in the container do not. Use object storage if source PDFs must survive restarts or be processed asynchronously.

## Local development commands

```powershell
python -m uvicorn main:app --host 127.0.0.1 --port 8000
python -m streamlit run streamlit_app.py
```
