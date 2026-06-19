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
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
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


async def close_database() -> None:
    global pool
    if pool is not None:
        await pool.close()
        pool = None


def get_pool() -> asyncpg.Pool:
    if pool is None:
        raise RuntimeError("Database has not been initialized")
    return pool
