import asyncio
from pathlib import Path

from celery import Celery

from app.config import get_settings
from app.database import close_database, get_pool, initialize_database
from app.services.indexing import prepare_document_bytes, store_documents

settings = get_settings()
celery_app = Celery("localrag", broker=settings.celery_broker_url)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    broker_connection_retry_on_startup=True,
    task_track_started=True,
)


async def process_job(job_id: int) -> None:
    await initialize_database()
    try:
        database = get_pool()
        await database.execute(
            """
            UPDATE ingestion_jobs
            SET status = 'processing', attempts = attempts + 1,
                error = NULL, updated_at = NOW()
            WHERE id = $1
            """,
            job_id,
        )
        files = await database.fetch(
            """
            SELECT id, filename, content_type, storage_path
            FROM ingestion_job_files
            WHERE job_id = $1 AND status != 'completed'
            ORDER BY id
            """,
            job_id,
        )

        for file in files:
            await database.execute(
                "UPDATE ingestion_job_files SET status = 'processing', error = NULL WHERE id = $1",
                file["id"],
            )
            data = Path(file["storage_path"]).read_bytes()
            prepared = await prepare_document_bytes(
                file["filename"], file["content_type"], data
            )
            stored = (await store_documents([prepared]))[0]
            await database.execute(
                """
                UPDATE ingestion_job_files
                SET status = 'completed', document_id = $2,
                    duplicate = $3, error = NULL
                WHERE id = $1
                """,
                file["id"],
                stored["id"],
                stored["duplicate"],
            )
            Path(file["storage_path"]).unlink(missing_ok=True)
            await refresh_job_progress(job_id)

        await refresh_job_progress(job_id, completed=True)
    finally:
        await close_database()


async def refresh_job_progress(job_id: int, completed: bool = False) -> None:
    await get_pool().execute(
        """
        UPDATE ingestion_jobs
        SET processed_files = (
                SELECT COUNT(*) FROM ingestion_job_files
                WHERE job_id = $1 AND status = 'completed'
            ),
            duplicate_files = (
                SELECT COUNT(*) FROM ingestion_job_files
                WHERE job_id = $1 AND duplicate = TRUE
            ),
            status = CASE WHEN $2 THEN 'completed' ELSE status END,
            updated_at = NOW()
        WHERE id = $1
        """,
        job_id,
        completed,
    )


async def mark_job_error(job_id: int, message: str, final: bool) -> None:
    await initialize_database()
    try:
        pool = get_pool()
        failed_paths = []
        if final:
            failed_paths = await pool.fetch(
                "SELECT storage_path FROM ingestion_job_files WHERE job_id = $1",
                job_id,
            )
        await pool.execute(
            """
            UPDATE ingestion_jobs
            SET status = $2, error = $3, updated_at = NOW()
            WHERE id = $1
            """,
            job_id,
            "failed" if final else "retrying",
            message[:1000],
        )
        await pool.execute(
            """
            UPDATE ingestion_job_files
            SET status = $2, error = $3
            WHERE job_id = $1 AND status = 'processing'
            """,
            job_id,
            "failed" if final else "queued",
            message[:1000],
        )
        for file in failed_paths:
            try:
                Path(file["storage_path"]).unlink(missing_ok=True)
            except OSError:
                pass
    finally:
        await close_database()


@celery_app.task(bind=True, name="app.worker.process_ingestion_job")
def process_ingestion_job(self, job_id: int) -> None:
    try:
        asyncio.run(process_job(job_id))
    except Exception as error:
        final = self.request.retries >= 2
        asyncio.run(mark_job_error(job_id, str(error), final))
        if final:
            raise
        raise self.retry(exc=error, countdown=2 ** (self.request.retries + 1))
