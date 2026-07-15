# Resume Positioning

## Project Title

LocalRAG Intelligent Document Retrieval Platform

## Short Description

Built a containerized Retrieval-Augmented Generation platform for private document search, source-grounded question answering, asynchronous ingestion, semantic retrieval, user authentication, and agent-based query routing.

## Resume Bullets

- Developed a full-stack RAG platform using React, TypeScript, FastAPI, PostgreSQL, pgvector, Redis, Celery, Ollama, optional OpenAI-compatible APIs, Docker, and Kubernetes.
- Built asynchronous document ingestion pipelines for PDF, DOCX, and TXT files with extraction, chunking, embeddings, duplicate detection, and retryable background jobs.
- Implemented semantic vector search and PostgreSQL full-text retrieval to generate source-grounded answers with retrieved evidence and similarity scores.
- Added Redis-backed retrieval caching with scoped cache keys and cache-hit metrics to improve repeated-query response latency.
- Added a retrieval benchmark script to measure request success rate, throughput, and latency percentiles for repeatable performance evaluation.
- Added secure user authentication with Argon2 password hashing, signed HTTP-only cookies, session handling, document isolation, and persistent conversation memory.
- Designed an agent planner that routes requests across search, summarization, analysis, conversation-memory, and clarification tools while exposing a tool trace for observability.

## Technical Keywords

Retrieval-Augmented Generation, RAG, Semantic Search, Vector Search, pgvector, PostgreSQL, FastAPI, React, TypeScript, Redis, Celery, Ollama, OpenAI APIs, Docker, Kubernetes, Authentication, Agentic AI, Benchmarking, Performance Testing.
