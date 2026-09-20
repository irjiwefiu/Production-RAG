# Render Deployment Guide

This guide deploys the current root application to Render using Gemini and Qdrant Cloud.

## Recommended Render setup

Start with **one Render Web Service** running Streamlit. This matches the current application behavior:

- Streamlit receives and stores the uploaded PDF.
- The app processes the PDF and creates embeddings.
- Vectors are persisted in Qdrant Cloud.
- Inngest is disabled on Render unless a separate production Inngest service is configured.

The local Inngest Dev Server is for development only. Do not use `npx inngest-cli dev` as the production process on Render.

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

INNGEST_ENABLED=false
INNGEST_DEV=0
```

Optional settings:

```text
FASTAPI_BASE_URL=http://127.0.0.1:8000
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

## 6. Inngest production architecture

The local workflow uses a PDF path such as `uploads/document.pdf`. That path exists only inside the process that received the upload. Therefore, separate Render services cannot share that path automatically.

For a production Inngest deployment, use this architecture:

1. Upload the PDF to durable object storage such as S3, Cloudflare R2, or Supabase Storage.
2. Send the object URL or object key in the Inngest event, instead of a local file path.
3. Run FastAPI as a separate Render Web Service.
4. Configure Streamlit with:

```text
FASTAPI_BASE_URL=https://<your-fastapi-service>.onrender.com
INNGEST_ENABLED=true
INNGEST_API_BASE=<your-inngest-api-url>
INNGEST_EVENT_API_BASE=<your-inngest-event-api-url>
```

5. Use Inngest Cloud or a separately managed Inngest-compatible production service. Do not rely on the in-memory local Inngest Dev Server for production data.

This upgrade also requires changing the ingestion payload and backend loader to download the PDF from object storage before parsing it.

## 7. Common Render problems

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
$env:INNGEST_DEV='1'
python -m uvicorn main:app --host 127.0.0.1 --port 8000

npx --ignore-scripts=false inngest-cli@latest dev -u http://127.0.0.1:8000/api/inngest --no-discovery

python -m streamlit run streamlit_app.py
```
