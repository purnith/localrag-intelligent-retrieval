# LocalRAG — Intelligent Document Retrieval Platform

LocalRAG is a local-first retrieval-augmented generation (RAG) application.
Users upload documents, ask questions in natural language, and receive answers
grounded in semantically retrieved document passages.

The complete stack runs locally with open-source software. Documents are not
sent to an external AI provider, and no paid API key is required.

## Features

- Upload and index batches of up to 10 PDF, DOCX, and TXT documents, 10 MB each
- Extract and split document text into overlapping chunks
- Generate embeddings locally with `nomic-embed-text`
- Store and search vectors with PostgreSQL and pgvector
- Retrieve passages by semantic similarity rather than exact keywords
- Generate grounded answers with Qwen 2.5 through Ollama
- Display retrieved source passages and similarity scores
- Check PostgreSQL, Redis, Ollama, and API availability concurrently
- Run the complete system with Docker Compose

## Architecture

```text
React + TypeScript
        |
        | REST/JSON
        v
FastAPI application
   |         |          |
   v         v          v
PostgreSQL  Redis      Ollama
+ pgvector  cache      Qwen + embedding model
```

### Ingestion workflow

```text
Document upload
  -> text extraction
  -> overlapping chunks
  -> local embeddings
  -> PostgreSQL/pgvector
```

### Question-answering workflow

```text
Question
  -> question embedding
  -> cosine-similarity search
  -> relevant document chunks
  -> grounded Qwen prompt
  -> answer with source evidence
```

## Technology stack

| Layer | Technology | Responsibility |
| --- | --- | --- |
| Frontend | React, TypeScript, Vite | Upload and question-answering interface |
| API | FastAPI, Pydantic | Validation, orchestration, and REST endpoints |
| Database | PostgreSQL, pgvector | Document metadata, chunks, and vector search |
| Cache | Redis | Foundation for caching and session state |
| AI runtime | Ollama | Local model serving |
| Generation model | Qwen 2.5 3B | Grounded natural-language answers |
| Embedding model | nomic-embed-text | 768-dimensional semantic embeddings |
| Infrastructure | Docker Compose | Reproducible local services and networking |

## Quick start

### Requirements

- Docker Desktop with WSL 2 on Windows
- At least 8 GB of RAM; 16 GB is recommended
- Approximately 5 GB of free disk space for images and models

### Start the services

```powershell
Copy-Item .env.example .env
docker compose up --build -d
```

Download the local models once:

```powershell
docker compose exec ollama ollama pull qwen2.5:3b
docker compose exec ollama ollama pull nomic-embed-text
```

Open the application:

- Web interface: http://localhost:5173
- Interactive API documentation: http://localhost:8000/docs
- Service health: http://localhost:8000/api/health

Stop the services:

```powershell
docker compose down
```

Docker volumes retain model and database data between restarts. To delete all
local project data intentionally, use `docker compose down --volumes`.

## API overview

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Report component availability |
| `POST` | `/api/documents` | Upload, extract, embed, and index a document |
| `POST` | `/api/documents/batch` | Upload and index multiple documents atomically |
| `GET` | `/api/documents` | List indexed documents |
| `POST` | `/api/search` | Retrieve semantically similar chunks |
| `POST` | `/api/ask` | Retrieve evidence and generate a grounded answer |

## Example

Upload `test-data/sample-policy.txt`, then ask:

> How many vacation days do employees receive, and when can new employees use them?

The system retrieves the relevant policy text and produces a concise answer
that references the source document.

## Repository structure

```text
.
├── backend/                 # FastAPI application and tests
│   ├── app/api/             # HTTP endpoints
│   ├── app/services/        # Extraction and Ollama integrations
│   └── tests/               # Unit tests
├── frontend/                # React and TypeScript interface
├── test-data/               # Synthetic demonstration document
├── compose.yaml             # Local service orchestration
└── .env.example             # Safe configuration template
```

## Current scope and limitations

This repository is a functional local RAG application and learning project. It
is not yet a production or fully distributed multi-agent system.

- Document ingestion currently runs inside the API request.
- Redis is connected and monitored but caching is not implemented yet.
- Authentication and per-user document authorization are not implemented.
- Scanned PDFs require OCR, which is not currently included.
- Vector search currently uses exact cosine distance without an approximate index.
- Local model quality and latency depend on available hardware.

## Roadmap

- Background ingestion workers and job status tracking
- Redis query caching and conversation sessions
- Hybrid keyword and vector retrieval
- Reranking and retrieval-quality evaluation
- Authentication and document-level authorization
- Specialized routing, retrieval, synthesis, and evaluation agents
- Load testing, observability, retries, and horizontal scaling

## Privacy and cost

The default configuration sends no documents to paid AI APIs. Ollama serves
both models locally. Docker image and model downloads require internet access,
but running the application does not incur API usage charges.

## License

Licensed under the [MIT License](LICENSE).
