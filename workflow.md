# Application Workflow

This project is a production-style Retrieval-Augmented Generation (RAG) app for answering questions from uploaded PDFs. The system combines a Streamlit front end, a FastAPI backend, optional Inngest workflow orchestration, vector storage with Qdrant, and a provider-aware LLM layer.

## 1. High-level architecture

The main workflow is:

1. User uploads a PDF in the Streamlit UI.
2. The app saves the file locally.
3. The document is split into text chunks.
4. Each chunk is converted to an embedding.
5. The embeddings are stored in Qdrant together with the source metadata.
6. When the user asks a question, the app embeds the question and retrieves the most relevant document chunks.
7. The retrieved chunks are used as context for a grounded answer.
8. The answer is returned to the UI and displayed with source names.

A simplified diagram:

```text
PDF Upload
   ↓
Streamlit UI
   ↓
Chunk + Embed pipeline
   ↓
Qdrant Vector DB
   ↓
Question embedding
   ↓
Top-k retrieval
   ↓
LLM answer with source context
   ↓
UI response
```

---

## 2. Main components

### Streamlit frontend
The app entry point is `streamlit_app.py`.

It does several things:
- lets the user configure model providers and API keys in the sidebar
- uploads PDFs
- triggers ingestion or query flows
- shows answers and source references
- handles fallback behavior when Inngest or backend services are unavailable

This UI is the main user-facing entry point for the application.

### FastAPI backend
The backend is defined in `main.py`.

It exposes two local API routes:
- `/api/local-ingest`: ingests a PDF into the vector store
- `/api/local-query-ai`: retrieves context and answers a question
- `/api/local-query-context`: returns context-only answers when generation is not available

The same file also exposes the Inngest workflow registration and the actual LLM generation logic.

### Inngest workflow engine
When `INNGEST_ENABLED` is turned on, the app uses Inngest to process ingestion and query jobs asynchronously.

The workflow includes:
- `rag/ingest_pdf` event
- `rag/query_pdf_ai` event
- an async function for each event

This gives the app a structured job-based workflow for PDF ingestion and query processing.

### Qdrant vector database
The vector storage logic is in `vector_db.py`.

It:
- connects to a remote Qdrant instance if available
- falls back to an embedded local Qdrant store at `QDRANT_PATH`
- creates a collection if it does not exist
- upserts chunk vectors with payloads like source and text
- searches for the nearest matching chunks using cosine similarity

### Chunking and embedding logic
The PDF processing and embedding code is in `data_loader.py`.

It does:
- uses `PDFReader` from LlamaIndex to read PDF text
- normalizes OCR-style formatting and whitespace issues
- splits the document into text chunks by `SentenceSplitter`
- converts each chunk to an embedding using the selected provider
- supports OpenAI, Gemini, Ollama, or a local deterministic hash fallback

---

## 3. Startup and configuration flow

When the app starts:

1. Environment variables are loaded from `.env` via `load_dotenv()`.
2. The sidebar asks the user to choose:
   - LLM provider (OpenAI, Gemini, Claude, Ollama, local)
   - embedding provider
   - model versions
   - whether to enable Inngest mode
3. The selected values are saved to `.env`.
4. The app checks whether the Inngest backend and local backend are reachable.
5. The app enters either:
   - Inngest mode, or
   - local fallback mode

### Inngest mode
If enabled, the Streamlit app emits events to the Inngest dev server. The Inngest functions then process the workflow asynchronously.

### Local mode
If Inngest is disabled or unavailable, the app falls back to direct API calls to the FastAPI endpoints and runs retrieval locally.

---

## 4. Ingestion workflow

This is the document ingestion path.

### Step 1: User uploads PDF
The user selects a PDF in the Streamlit UI. The file is saved in the `uploads` directory.

### Step 2: Event or direct API call
Depending on configuration:
- In Inngest mode, the app sends a `rag/ingest_pdf` event with:
  - `pdf_path`
  - `source_id` (usually the file name)
- In local mode, the app calls `/api/local-ingest` directly

### Step 3: PDF loading and chunking
In `main.py` or `data_loader.py`, the code:
- loads the PDF
- extracts text
- normalizes it
- uses a sentence splitter to create smaller chunks

This chunking step is critical because retrieval works better on smaller, semantically meaningful text pieces.

### Step 4: Embedding generation
Each chunk is sent to the configured embedding provider:
- OpenAI embedding API
- Gemini embedding API
- Ollama embedding endpoint
- local generated embeddings as fallback

The embedding model returns a vector for each chunk.

### Step 5: Deterministic IDs and payload creation
Each chunk gets a stable UUID based on the source ID and chunk index. This makes re-ingestion idempotent and avoids duplicate documents from multiple runs.

Each stored record includes:
- vector
- source file name
- original text chunk

### Step 6: Upsert to Qdrant
The app calls `get_qdrant_storage().upsert(...)`.

This writes records into the vector collection. Qdrant indexes them by vector and stores metadata such as the source file.

### Step 7: Ingestion result
The response returns the number of chunks successfully ingested.

---

## 5. Query workflow

This is the question-answering flow.

### Step 1: User asks a question
The user submits a question in the Streamlit interface with a selected `top_k` value.

### Step 2: Event or direct query call
If Inngest is enabled:
- the UI sends a `rag/query_pdf_ai` event
- the payload includes:
  - question
  - top_k
  - optional `source_hint`

If local mode is active:
- the UI calls `/api/local-query-ai` directly

### Step 3: Question embedding
The app embeds the user question with the same embedding model used for document ingestion.

### Step 4: Vector search in Qdrant
The vector database searches for the nearest matching chunks.

The code uses:
- `search_limit = min(max(top_k, fallback_bound), 20)`
- a source filter if a source hint is present
- a ranking function that boosts keyword overlap and skill-related matches

This yields the most relevant text chunks and their source names.

### Step 5: Context assembly
The retrieved chunks are turned into a prompt block like:

```text
Context:
- chunk 1
- chunk 2
- chunk 3

Question: <user question>
```

This is the evidence used to answer.

### Step 6: Answer generation
The app then calls `generate_answer(...)`.

That function:
- reads the selected provider from environment variables
- calls the appropriate LLM API (OpenAI, Gemini, Claude, Ollama)
- passes the retrieved context to the model with a strict system prompt
- tells the model to answer only from the given context

The system prompt is intentionally strict:
- answer only from the provided context
- if the answer is not in the context, say exactly: "I don't know based on provided documents."

### Step 7: Fallback answer generation
If the configured LLM call fails or returns nothing:
- the app attempts a local context-based answer
- the fallback logic extracts evidence-only snippets and responds from retrieved context without making up facts

This is a major safety mechanism in the app.

### Step 8: Response to UI
The answer along with the list of sources is returned to Streamlit and displayed to the user.

---

## 6. RAG ranking and relevance logic

The app is not just returning the first vector results blindly. It applies more logic before final answer generation.

The function `_rank_records(...)` does the following:
- extracts keywords from the user's question
- lowercases and normalizes the retrieved text
- measures overlap between question keywords and chunk text
- boosts skill/experience-related matches
- favors chunks with stronger vector similarity
- removes duplicate chunks
- keeps only the best top-k results

This is important for resume-style and skill-based queries, where the user might ask things like:
- "What technologies do you know?"
- "What experience do you have in Python?"
- "List your skills and tools."

The code intentionally boosts resume/skills wording so the system can surface the most relevant evidence.

---

## 7. Evidence-only fallback behavior

A core idea in this app is to avoid hallucinations.

The app uses strict evidence handling:
- if the model cannot answer from retrieved text, it should refuse
- if LLM provider is unavailable, it falls back to context-only answer generation
- if all else fails, it returns a polite statement such as:
  - "I don't know based on provided documents."

This makes the system safer than a typical chat model that answers from general knowledge.

---

## 8. Local fallback mechanics

The app is designed to work even when components are unavailable.

### If Qdrant is unavailable
The code tries remote Qdrant first. If that fails, it creates a local embedded Qdrant instance at `QDRANT_PATH`.

### If embedding provider fails
The app falls back to a deterministic hash-based vector generator. This is not semantically rich, but it keeps the pipeline functional when external services are down.

### If the LLM provider fails
The app tries:
- provider-specific model generation
- local answer generation using retrieved context
- evidence-only answer fallback

### If Inngest is unavailable
The app simply calls the local FastAPI endpoints instead of using async workflow events.

This means the system is resilient in real-world degraded environments.

---

## 9. End-to-end data flow

Here is the full round-trip:

```text
User uploads PDF
   ↓
Streamlit saves file to uploads/
   ↓
FastAPI / Inngest receives ingest request
   ↓
PDF text is extracted
   ↓
Text is normalized and split into chunks
   ↓
Chunks are embedded
   ↓
Vectors + payloads are upserted to Qdrant
   ↓
User asks question
   ↓
Question is embedded
   ↓
Top-k chunks are retrieved from Qdrant
   ↓
Relevant chunks are ranked and filtered
   ↓
LLM receives strict context-only prompt
   ↓
Answer is generated from evidence
   ↓
Sources are returned to UI
```

---

## 10. Why this architecture works well

This project is designed for practical document intelligence rather than a simple notebook demo.

It is useful because it contains:
- multi-provider LLM support
- multi-provider embedding support
- flexible local fallback logic
- deterministic IDs for re-ingestion safety
- vector search for semantic retrieval
- grounded answer generation based only on retrieved context
- robust UI fallback behavior and source attribution

This makes it a realistic production-oriented RAG workflow for resume analysis, document Q&A, and knowledge retrieval.

---

## 11. Practical summary

The app works like this in one sentence:

A PDF is uploaded, split into chunks, embedded, stored in Qdrant, and later retrieved by semantic similarity to answer user questions using only the retrieved document evidence.

That is the full RAG workflow implemented by this project.
