# Architecture

LocalRAG is a service-oriented Retrieval-Augmented Generation platform built for local document intelligence.

```text
React + TypeScript frontend
        |
        | REST/JSON
        v
FastAPI backend
  |-- Auth/session APIs
  |-- Document ingestion APIs
  |-- Retrieval and agent APIs
  |-- Redis retrieval cache and cache metrics
        |
        | queues ingestion jobs
        v
Redis + Celery worker
        |
        | extracts, chunks, embeds
        v
PostgreSQL + pgvector
        |
        | retrieved evidence
        v
Ollama or OpenAI-compatible LLM runtime
```

## Core Flows

### Document Ingestion

1. User uploads PDF, DOCX, or TXT files.
2. Backend creates an ingestion job.
3. Celery worker extracts text and chunks documents with overlap.
4. Embeddings are generated through Ollama.
5. Chunks and vectors are stored in PostgreSQL with pgvector.

### Question Answering

1. User asks a question.
2. Backend resolves user, document, and conversation context.
3. Semantic search retrieves relevant chunks.
4. Redis cache serves repeated scoped retrieval requests when available.
5. The agent planner chooses search, summary, analysis, memory, or clarification behavior.
6. Ollama or an OpenAI-compatible provider generates grounded answers with source evidence.

## Persistence

- PostgreSQL stores users, documents, chunks, conversations, messages, and ingestion jobs.
- pgvector stores semantic embeddings for retrieval.
- Redis supports background job orchestration.
- Docker volumes persist local development data.

## Deployment

The project supports Docker Compose for local development and Kubernetes manifests for local cluster deployment with independently managed workloads.
