import asyncpg

from app.config import get_settings

settings = get_settings()
pool: asyncpg.Pool | None = None


async def initialize_database() -> None:
    global pool
    pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=10)
    async with pool.acquire() as connection:
        await connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id BIGSERIAL PRIMARY KEY,
                filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                content_hash TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        await connection.execute(
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_hash TEXT"
        )
        await connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS documents_content_hash_idx
            ON documents(content_hash)
            WHERE content_hash IS NOT NULL
            """
        )
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS document_chunks (
                id BIGSERIAL PRIMARY KEY,
                document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                embedding vector(768) NOT NULL,
                UNIQUE(document_id, chunk_index)
            )
            """
        )
        await connection.execute(
            """
            CREATE INDEX IF NOT EXISTS document_chunks_content_fts_idx
            ON document_chunks
            USING GIN(to_tsvector('english', content))
            """
        )
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ingestion_jobs (
                id BIGSERIAL PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'queued',
                total_files INTEGER NOT NULL,
                processed_files INTEGER NOT NULL DEFAULT 0,
                duplicate_files INTEGER NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 0,
                error TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ingestion_job_files (
                id BIGSERIAL PRIMARY KEY,
                job_id BIGINT NOT NULL REFERENCES ingestion_jobs(id) ON DELETE CASCADE,
                filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                storage_path TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                document_id BIGINT REFERENCES documents(id) ON DELETE SET NULL,
                duplicate BOOLEAN NOT NULL DEFAULT FALSE,
                error TEXT
            )
            """
        )


async def close_database() -> None:
    global pool
    if pool is not None:
        await pool.close()
        pool = None


def get_pool() -> asyncpg.Pool:
    if pool is None:
        raise RuntimeError("Database has not been initialized")
    return pool
