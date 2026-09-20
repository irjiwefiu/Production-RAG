# Project Understanding: Production-grade-RAG

This repository is a document intelligence and Retrieval-Augmented Generation (RAG) project built for PDF ingestion, vector storage, semantic retrieval, and grounded answers. It combines a root-level application with a more structured package under `rag-engine`.

The project is designed to show a practical production-style RAG architecture rather than a notebook-only demo.

---

## 1) Repository overview

The project has two layers:

1. Root application layer
   - quick setup
   - fast iteration
   - Streamlit UI + FastAPI backend
   - local fallback and dev workflow

2. Packaged production-style layer
   - `rag-engine/`
   - modular API, core logic, models, UI, tests, and Docker setup

This means the repo is both a developer-friendly prototype and a modular production-oriented service.

---

## 2) Root-level files

### README.md
Purpose:
- Project overview
- usage instructions
- setup and troubleshooting
- architecture summary

What it explains:
- this is a PDF-based RAG system
- the system uses Qdrant for vector storage and retrieval
- supports multiple providers like OpenAI, Gemini, Claude, Ollama, and local fallback
- includes Streamlit UI and FastAPI backend
- includes Inngest workflow orchestration

This file is the entry point for understanding the project at a high level.

---

### pyproject.toml
Purpose:
- package metadata
- Python version requirement
- dependency declarations

Main dependencies:
- fastapi
- streamlit
- uvicorn
- qdrant-client
- openai
- google-generativeai
- anthropic
- llama-index-core
- llama-index-readers-file
- inngest
- python-dotenv
- requests

This tells us the app is designed around multiple AI providers and a vector DB.

---

### main.py
Purpose:
- central backend logic
- orchestrates retrieval + LLM answer generation
- handles workflow events from Inngest

Key responsibilities:
- loads environment variables via `load_dotenv()`
- reads LLM config from environment
- routes requests to OpenAI, Gemini, Claude, Ollama, or local mode
- retrieves relevant chunks from Qdrant
- generates responses using context-only prompts
- defines workflow functions for document ingestion and querying

Important functions:

#### `_ollama_headers()`
Returns bearer auth headers for Ollama requests when `OLLAMA_API_KEY` exists.

#### `_get_llm_config()`
Reads environment variables such as:
- `LLM_PROVIDER`
- `OPENAI_MODEL`
- `GEMINI_MODEL`
- `CLAUDE_MODEL`
- `OLLAMA_MODEL`
- `OLLAMA_BASE_URL`

This is used to dynamically select the LLM backend.

#### `_compact_spaced_letters(text: str)`
Normalizes OCR-style broken words such as:
- `A c h i e v e d`
into:
- `Achieved`

This improves text matching quality for PDF-derived text.

#### `_normalize_for_match(text: str)`
Lowercases and normalizes text so keyword matching is consistent.

#### `_extract_keywords(question: str)`
- removes stop words
- keeps meaningful tokens
- returns ordered keywords for ranking retrieved chunks

#### `_is_skill_question(question: str)`
Checks whether a question is about skills, tools, stack, technologies, experience, etc.

#### `_rank_records(question, records, top_k)`
Ranks retrieved records using:
- keyword overlap
- skill-related bonus scoring
- vector score from Qdrant

This improves result ordering when answering questions about technologies or experience.

#### `_evidence_only_answer(question, contexts)`
Builds an answer only using context snippets. It avoids invented facts and returns evidence-based output.

#### `_local_answer(user_content)`
Fallback logic used when the configured provider is unavailable or returns no result.

#### `generate_answer(user_content: str)`
The main answer-generation function.
It routes to:
- OpenAI `chat.completions.create`
- Gemini `GenerativeModel.generate_content`
- Anthropic `messages.create`
- Ollama REST chat API
- local fallback mode

This is the main LLM abstraction layer.

The file also defines Inngest workflows triggered by events like:
- `rag/ingest_pdf`
- `rag/query_pdf_ai`

These are used to orchestrate ingestion and query jobs in a durable way.

Why it matters:
- this is the core AI orchestration logic
- it enforces evidence-first answer generation
- it supports provider switching without code changes

---

### streamlit_app.py
Purpose:
- front-end interface for the application
- upload PDF and ask questions

Main responsibilities:
- model settings in sidebar
- save credentials to `.env`
- discover Ollama models
- allow provider selection
- upload PDFs to `uploads/`
- trigger ingestion events
- trigger query events

Important helper functions:

#### `_save_env(key, value)`
Persists environment settings to `.env` using `set_key()`.

#### `_llm_model_key(provider)`
Returns the correct env variable name for the selected LLM model.

#### `_embed_model_key(provider)`
Returns the env variable name for the selected embedding model.

#### `_fetch_ollama_models()`
Calls the Ollama tags API and returns available models.

#### `_llm_models_for(provider)`
Returns candidate models for each provider.

#### `_embed_models_for(provider)`
Returns embedding models for each provider.

#### `_render_model_settings()`
Renders sidebar controls for:
- LLM provider
- embedding provider
- model versions
- API keys
- Inngest toggle

#### `save_uploaded_pdf(file)`
Saves the uploaded PDF into a local folder named `uploads`.

#### `send_rag_ingest_event(pdf_path)`
Sends an Inngest event to begin document ingestion.

#### `send_rag_query_event(question, top_k, source_hint=None)`
Sends a question and retrieval settings to the workflow system.

Why it matters:
- this gives users an interface for using the system without needing command-line tools
- it also makes the setup easier for experimentation and demos

---

### data_loader.py
Purpose:
- PDF ingestion and embedding pipeline for the root app

Main responsibilities:
- load text from PDF files
- normalize extracted text
- split documents into chunks
- generate embeddings for each chunk

Important components:

#### `_ollama_headers()`
Used for Ollama authentication when needed.

#### `_default_embed_dim(provider)`
Chooses expected embedding size depending on provider.

#### `_openai_client()`
Constructs an OpenAI client from `OPENAI_API_KEY`.

#### `_get_embed_config()`
Reads environment configuration for:
- embedding provider
- embedding model
- Ollama URL
- Ollama embedding model
- embedding dimension

#### `_hash_embedding(text, dim)`
Creates deterministic pseudo-embedding when an external API is unavailable.
This is a local fallback strategy.

#### `SentenceSplitter`
Used to split large text into chunks with controlled overlap.

#### `_normalize_pdf_text(text)`
Cleans OCR and formatting artifacts from extracted PDF text.

#### `load_and_chunk_pdf(path)`
Loads PDF content and splits it into chunk strings.

#### `embed_texts(texts)`
Generates embedding vectors from a list of text chunks.
Supports:
- OpenAI embeddings
- Gemini embeddings
- Ollama embeddings
- local hash fallback

Why it matters:
- this is where raw documents become searchable vector data
- chunk quality directly affects retrieval quality

---

### vector_db.py
Purpose:
- vector storage layer using Qdrant

Main responsibilities:
- connect to Qdrant
- create collections
- insert vectors and metadata
- search nearest neighbors
- store shared client singleton

Important parts:

#### `QdrantStorage._default_dim()`
Chooses expected vector dimension based on provider.

#### `QdrantStorage._create_local_client(path)`
Creates a local embedded Qdrant client when remote Qdrant is not available.

#### `QdrantStorage.__init__()`
Tries remote Qdrant first, then falls back to the local file-based storage path.

#### `QdrantStorage.upsert(ids, vectors, payloads)`
Stores vector entries in Qdrant as points.

#### `QdrantStorage.search(query_vector, top_k=5)`
Runs vector search and returns:
- contexts
- source list
- metadata records
- scores

#### `get_qdrant_storage()`
Returns the shared singleton instance.

#### `_close_shared_store()`
Closes the Qdrant storage at process exit.

Why it matters:
- this is the retrieval backend for the root project
- it makes the system resilient to infrastructure changes

---

### custom_types.py
Purpose:
- Pydantic models for the root project

Important models:

#### `RAGChunkAndSrc`
Stores:
- `chunks: list[str]`
- `source_id: str`

#### `RAGUpsertResult`
Used for ingestion status response.

#### `RAGSearchResult`
Used for retrieval search response and includes:
- `contexts`
- `sources`

#### `RAQQueryResult`
Contains:
- `answer`
- `sources`
- `num_contexts`

Why it matters:
- defines input/output contracts for the system
- ensures consistent response objects and easier validation

---

### doc.md
Purpose:
- detailed conceptual documentation
- written product walkthrough

This file explains the project as if it were a “document hospital”:
- front door = main.py
- triage nurse = data_loader.py
- medical records room = vector_db.py
- patient chart = custom_types.py
- waiting room = streamlit_app.py
- hospital blueprint = rag-engine package

It also explains production patterns like:
- idempotent doc ingestion
- provider abstraction
- graceful degradation
- vector retrieval with LLM grounding

This is the documentation file for understanding the design philosophy behind the system.

---

## 3) Files in the packaged app: rag-engine

### rag-engine/README.md
Purpose:
- explains the package structure
- serves as package-level overview for developers

It describes where the application logic is organized:
- config.py
- models/schemas.py
- core/*
- api/*
- ui/streamlit_app.py

This acts as the package-level map.

---

### rag-engine/pyproject.toml
Purpose:
- package metadata for the modular project

Key settings:
- name: `rag-engine`
- Python requirement: >=3.11
- dependencies for FastAPI, OpenAI, Qdrant, Streamlit, pydantic, uvicorn
- optional dev dependencies: pytest, ruff, httpx

It is configured for a proper Python package and test workflow.

---

### rag-engine/src/rag_engine/config.py
Purpose:
- environment-driven settings for the package app

Key classes:

#### `EmbeddingProvider` (enum)
Possible values:
- `openai`
- `huggingface`

#### `Settings(BaseSettings)`
Defines application configuration such as:
- `openai_api_key`
- `llm_model`
- `llm_temperature`
- `embedding_provider`
- `embedding_model`
- `embedding_dimensions`
- `qdrant_url`
- `qdrant_collection_name`
- `chunk_size`
- `chunk_overlap`
- `supported_formats`
- `retrieval_top_k`
- `similarity_threshold`
- `api_host`
- `api_port`
- `log_level`
- `cors_origins`

It includes validation for overlap < chunk size.

This is the centralized configuration system for the production-style package.

---

### rag-engine/src/rag_engine/models/schemas.py
Purpose:
- define the API contracts for the packaged app

Key models:

#### `DocumentStatus`
Enum values:
- `processing`
- `indexed`
- `failed`

#### `DocumentUploadResponse`
Returned after a file is uploaded or processed.
Contains:
- document id
- filename
- status
- chunks_created
- processing_time_ms
- created_at

#### `QueryRequest`
Request payload for question-answering.
Contains:
- `question`
- `top_k`
- `similarity_threshold`

#### `SourceDocument`
Single relevant source item with metadata such as:
- content
- filename
- page number
- similarity score
- chunk id

#### `QueryResponse`
Contains:
- answer
- sources
- query_time_ms
- tokens_used
- model
- confidence

#### `HealthResponse`
Contains app and Qdrant status metrics.

This file is important because it explains how data moves across the API.

---

### rag-engine/src/rag_engine/core/document_loader.py
Purpose:
- load and chunk documents for indexing

Important class:

#### `DocumentLoadError`
Raised when a file cannot be loaded or validated.

#### `DocumentProcessor`
This is the main processor class.

Important features:

##### `LOADER_MAP`
Maps file extensions to loaders:
- `.pdf` -> PyPDFLoader
- `.txt` -> TextLoader
- `.md` -> UnstructuredMarkdownLoader

##### `validate_file(filename, file_size_bytes)`
Checks:
- file extension supported?
- size within allowed limit?

##### `compute_hash(content)`
Generates SHA-256 hash for deduplication.

##### `load_and_chunk(file_path, filename)`
- loads file content
- extracts documents
- enriches metadata
- splits into chunks using `RecursiveCharacterTextSplitter`
- returns document chunks and elapsed time

Design decisions:
- recursive splitting preserves context better than a naive split
- metadata gets added at both document and chunk level
- deduplication prevents re-indexing identical content

This is a more robust and structured version of the root data-loading logic.

---

### rag-engine/src/rag_engine/core/embeddings.py
Purpose:
- create embeddings using OpenAI

Function:

#### `embed_texts(texts, client=None)`
- returns empty list for empty input
- uses `OpenAI(api_key=settings.openai_api_key)` by default
- creates embeddings with the configured model
- returns list of embedding vectors

This isolates AI embedding generation into a dedicated module.

---

### rag-engine/src/rag_engine/core/vector_store.py
Purpose:
- Qdrant vector store manager

Key class:

#### `VectorStoreError`
Raised when the vector store cannot initialize or query properly.

#### `VectorStoreManager`
Main responsibilities:
- lazy initialization of Qdrant client
- create vector store using `QdrantVectorStore`
- build embeddings with `OpenAIEmbeddings`
- perform health checks
- index document chunks
- search by similarity and threshold

Key methods:

##### `client`
Creates the Qdrant client if needed.

##### `store`
Creates the vector store wrapper around Qdrant.

##### `health_check()`
Checks if Qdrant is reachable and whether the collection exists.
Returns:
- connected
- documents_indexed
- collection_exists

##### `index_documents(chunks)`
Indexes the chunks into Qdrant and returns IDs and time spent.

##### `search(query, top_k, score_threshold)`
Searches the vector store, filters results by minimum score, and returns matching docs with similarity values.

This file is central to retrieval in the packaged app.

---

### rag-engine/src/rag_engine/core/rag_chain.py
Purpose:
- intended orchestration layer for the packaged RAG system

The file contains logic that is conceptually meant to unify:
- document loading
- chunk retrieval
- vector search
- answer generation

In practice, this file appears to overlap with the vector store manager and may need further cleanup or refactoring.

This is still the conceptual heart of the system: retrieval + generation workflow.

---

### rag-engine/src/rag_engine/api/app.py
Purpose:
- create and configure the FastAPI application

Important elements:

#### `lifespan(app)`
Runs application startup/shutdown events.

#### `create_app()`
- creates FastAPI instance with title and description
- adds CORS middleware
- includes route modules for:
  - health
  - documents
  - query

#### `app = create_app()`
Creates the app object used by uvicorn.

This is the API assembly point.

---

### rag-engine/src/rag_engine/api/routes/health.py
Purpose:
- `/health` endpoint

Method:

#### `health_check()`
Returns:
- status
- qdrant_connected
- documents_indexed
- uptime_seconds
- version

This is used for monitoring and container health checks.

---

### rag-engine/src/rag_engine/api/routes/documents.py
Purpose:
- document ingestion API

Method:

#### `ingest_document(payload)`
- creates a `RAGChain`
- calls `ingest_pdf(pdf_path, source_id)`
- maps `FileNotFoundError` to 404
- maps `ValueError` to 400

This is the document ingestion endpoint.

---

### rag-engine/src/rag_engine/api/routes/query.py
Purpose:
- question-answering API

Method:

#### `query_documents(request)`
- accepts `QueryRequest`
- calls `rag_chain.query(request)`
- returns `QueryResponse`
- maps vector store errors to HTTP 503
- maps other exceptions to 500

This is the central query endpoint.

---

### rag-engine/src/rag_engine/api/middleware/error_handler.py
Purpose:
- central error management for API endpoints

Functions:

#### `register_exception_handlers(app)`
Registers:
- `HTTPException` handler
- generic `Exception` handler

It converts exceptions to JSON responses with proper status codes.

---

### rag-engine/src/rag_engine/api/middleware/logging.py
Purpose:
- request logging middleware

Class:

#### `LoggingMiddleware(BaseHTTPMiddleware)`
Measures request duration and logs:
- method
- path
- status code
- elapsed time in ms

This helps with debugging and monitoring API traffic.

---

### rag-engine/src/rag_engine/ui/streamlit_app.py
Purpose:
- packaged UI for interacting with the API

Main functionality:
- save uploaded PDF to `uploads/`
- call `/documents/ingest`
- call `/query`
- show answer and sources in the UI

This is a simplified front-end for the modular package.

---

### rag-engine/src/rag_engine/utils/logger.py
Purpose:
- configure Python logging

Functions:

#### `setup_logging(level=logging.INFO)`
Sets logging format and level.

#### `get_logger(name)`
Returns a logger instance by name.

This is reused across files for consistent logs.

---

## 4) Test files

### rag-engine/tests/conftest.py
Purpose:
- ensures the `src` directory is on Python path
- allows tests to import `rag_engine` modules cleanly

---

### rag-engine/tests/unit/test_document_loader.py
Purpose:
- verifies chunking returns at least one chunk for a non-empty input

Test:

#### `test_chunk_texts_returns_chunks_for_non_empty_input()`
Checks that chunking creates chunks from text.

---

### rag-engine/tests/unit/test_rag_chain.py
Purpose:
- checks the result structure for a query result model

Test:

#### `test_rag_query_result_shape()`
Ensures `RAGQueryResult` contains answer and a number of contexts.

---

### rag-engine/tests/unit/test_vector_store.py
Purpose:
- verifies Qdrant-like store logic creates collection and upserts points

It uses a fake client object to test:
- collection creation
- upsert operation

---

### rag-engine/tests/integration/test_api.py
Purpose:
- checks that the health endpoint returns successful response

This validates that the FastAPI app loads and responds correctly.

---

## 5) Docker files

### rag-engine/docker/docker-compose.yml
Purpose:
- runs Qdrant and the API together

Service definitions:
- `qdrant` container
- `rag-engine` container

It sets port mapping and persistent volume for Qdrant storage.

---

### rag-engine/docker/Dockerfile
Purpose:
- builds the application in a container

Flow:
- installs Python and build tools
- installs project dependencies
- copies project source
- exposes port 8000
- runs uvicorn on startup

This is the deployment package for the app.

---

## 6) How everything connects

The full data flow of the project is:

1. User uploads document via Streamlit UI
2. PDF is stored in `uploads/`
3. Document loader extracts and cleans the text
4. Text is split into chunks
5. Embeddings are generated for each chunk
6. Qdrant stores vector entries with metadata
7. User asks a question
8. The question is embedded
9. Qdrant finds similar chunks
10. Top chunks are passed to the LLM
11. The model answers using only retrieved context

This is the core idea behind RAG.

---

## 7) Main design ideas of the project

- multi-provider AI support
- local fallback mode
- modular package architecture
- document ingestion and embedding pipeline
- Qdrant for semantic retrieval
- production-oriented API structure
- environment-based configuration
- test coverage for key modules
- Docker-based deployment

---

## 8) Overall conclusion

This repository is not a simple demo; it is a practical document intelligence system designed around real-world RAG architecture. The root app is a fast developer workflow, while the `rag-engine` package is the more structured production-style version.

The key concept is simple:
- ingest documents
- chunk them
- embed them
- search semantically
- answer using retrieved evidence

That is the essence of a modern RAG system.
