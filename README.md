# LocalRAG — Intelligent Document Retrieval Platform

LocalRAG is a containerized retrieval-augmented generation (RAG) platform for
multi-document knowledge retrieval. It ingests, chunks, and embeds documents,
combines semantic vector search with PostgreSQL full-text search, and generates
answers grounded in retrieved source passages.

The system uses a service-oriented architecture built with React, FastAPI,
PostgreSQL/pgvector, Redis, Ollama, Docker Compose, and Kubernetes.

## Features

- Upload and index batches of up to 10 PDF, DOCX, and TXT documents, 10 MB each
- Extract and split document text into overlapping chunks
- Generate semantic embeddings with `nomic-embed-text`
- Store and search vectors with PostgreSQL and pgvector
- Retrieve passages by semantic similarity rather than exact keywords
- Generate grounded answers with Qwen 2.5 through Ollama
- Display retrieved source passages and similarity scores
- Manage, select, and delete indexed documents
- Prevent duplicate indexing with content hashes
- Combine vector similarity with PostgreSQL full-text matching
- Filter weak matches and duplicate retrieved passages
- Process document ingestion through a Redis-backed Celery worker
- Track queued, processing, retrying, completed, and failed jobs
- Retry transient ingestion failures with exponential backoff
- Check PostgreSQL, Redis, Ollama, and API availability concurrently
- Run the complete system with Docker Compose
- Deploy the platform to a local Kubernetes cluster with persistent storage,
  resource limits, health probes, and independently managed workloads

## Architecture

```text
React + TypeScript
        |
        | REST/JSON
        v
FastAPI application ---> Redis broker ---> Celery workers
   |                                          |
   v                                          v
PostgreSQL + pgvector <-------------------- Ollama
```

### Ingestion workflow

```text
Document upload
  -> persistent job record
  -> Redis task queue
  -> Celery worker
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
| Worker | Celery | Background ingestion, progress, and retry handling |
| AI runtime | Ollama | Model serving and inference |
| Generation model | Qwen 2.5 3B | Grounded natural-language answers |
| Embedding model | nomic-embed-text | 768-dimensional semantic embeddings |
| Infrastructure | Docker Compose, Kubernetes, kind | Container orchestration, service discovery, storage, and workload management |

## Quick start

### Requirements

- Docker Desktop with WSL 2 on Windows
- At least 8 GB of RAM; 16 GB is recommended
- Approximately 5 GB of available disk space for images and models

### Start the services

```powershell
Copy-Item .env.example .env
docker compose up --build -d
```

Download the models once:

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

## Kubernetes deployment

The Kubernetes configuration runs each platform component as an independently
managed workload in the `localrag` namespace. PostgreSQL runs as a StatefulSet;
the API, worker, frontend, Redis, and Ollama run as Deployments. Persistent
volume claims retain database, queue, model, and staged-upload data.

### Requirements

- Docker Desktop
- `kubectl`
- `kind`
- At least 12 GB of memory available to Docker Desktop; 16 GB is recommended

Deploy the platform from PowerShell:

```powershell
.\scripts\deploy-kubernetes.ps1
```

The first deployment downloads the generation and embedding models and can take
several minutes. Once the workloads are ready, expose the web and API services:

```powershell
.\scripts\port-forward-kubernetes.ps1
```

Inspect the deployment:

```powershell
kubectl get all,pvc -n localrag
kubectl logs deployment/backend -n localrag
kubectl logs deployment/worker -n localrag
```

Delete the local cluster when it is no longer needed:

```powershell
.\scripts\delete-kubernetes.ps1
```

## API overview

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Report component availability |
| `POST` | `/api/documents` | Upload, extract, embed, and index a document |
| `POST` | `/api/documents/batch` | Upload and index multiple documents atomically |
| `POST` | `/api/documents/jobs` | Queue an asynchronous document-ingestion job |
| `GET` | `/api/documents/jobs/{id}` | Read ingestion progress and file-level status |
| `GET` | `/api/documents` | List indexed documents |
| `DELETE` | `/api/documents/{id}` | Delete a document and its chunks |
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

The current implementation supports Docker Compose and a single-node Kubernetes
deployment. The architecture is structured for incremental extraction of
workers, retrieval services, and agent workflows as operational requirements
grow.

- Redis is connected and monitored but caching is not implemented yet.
- Authentication and per-user document authorization are not implemented.
- Scanned PDFs require OCR, which is not currently included.
- Vector search currently uses exact cosine distance without an approximate index.
- Model quality and inference latency depend on available hardware.

## Roadmap

- Redis query caching and conversation sessions
- Configurable retrieval thresholds and local reranking
- Reranking and retrieval-quality evaluation
- Authentication and document-level authorization
- Specialized routing, retrieval, synthesis, and evaluation agents
- Load testing, observability, retries, and horizontal scaling

## Deployment and data boundary

Ollama hosts generation and embedding models within the deployment boundary.
Document extraction, vectorization, retrieval, and answer generation are
performed by the application services defined in Docker Compose.

## License

Licensed under the [MIT License](LICENSE).
