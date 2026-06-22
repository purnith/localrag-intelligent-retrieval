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
            CREATE TABLE IF NOT EXISTS users (
                id BIGSERIAL PRIMARY KEY,
                display_name TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        await connection.execute(
            "INSERT INTO users(display_name) SELECT 'Default User' WHERE NOT EXISTS (SELECT 1 FROM users)"
        )
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
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS user_id BIGINT"
        )
        await connection.execute(
            "UPDATE documents SET user_id = (SELECT id FROM users ORDER BY id LIMIT 1) WHERE user_id IS NULL"
        )
        await connection.execute("ALTER TABLE documents ALTER COLUMN user_id SET NOT NULL")
        await connection.execute(
            """
            DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'documents_user_id_fkey') THEN
                    ALTER TABLE documents ADD CONSTRAINT documents_user_id_fkey
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
                END IF;
            END $$
            """
        )
        await connection.execute("DROP INDEX IF EXISTS documents_content_hash_idx")
        await connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS documents_user_content_hash_idx
            ON documents(user_id, content_hash)
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
        await connection.execute(
            "ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS user_id BIGINT"
        )
        await connection.execute(
            "UPDATE ingestion_jobs SET user_id = (SELECT id FROM users ORDER BY id LIMIT 1) WHERE user_id IS NULL"
        )
        await connection.execute("ALTER TABLE ingestion_jobs ALTER COLUMN user_id SET NOT NULL")
        await connection.execute(
            """
            DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ingestion_jobs_user_id_fkey') THEN
                    ALTER TABLE ingestion_jobs ADD CONSTRAINT ingestion_jobs_user_id_fkey
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
                END IF;
            END $$
            """
        )
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id BIGSERIAL PRIMARY KEY,
                conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                sources JSONB,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        await connection.execute(
            "CREATE INDEX IF NOT EXISTS conversations_user_updated_idx ON conversations(user_id, updated_at DESC)"
        )
        await connection.execute(
            "CREATE INDEX IF NOT EXISTS messages_conversation_created_idx ON messages(conversation_id, created_at)"
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
