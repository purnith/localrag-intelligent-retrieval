from pathlib import Path
from shutil import rmtree
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status

from app.config import get_settings
from app.database import get_pool
from app.services.indexing import prepare_document_bytes, store_documents
from app.worker import process_ingestion_job

router = APIRouter(prefix="/api/documents", tags=["documents"])
settings = get_settings()
MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_BATCH_FILES = 10
SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt"}


async def read_upload(file: UploadFile) -> tuple[str, str, bytes]:
    filename = Path(file.filename or "document").name
    if Path(filename).suffix.lower() not in SUPPORTED_SUFFIXES:
        raise HTTPException(
            400, f"{filename}: supported file types are PDF, DOCX, and TXT"
        )

    data = await file.read(MAX_FILE_SIZE + 1)
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(413, f"{filename}: file must be 10 MB or smaller")
    return filename, file.content_type or "application/octet-stream", data


def validate_batch(files: list[UploadFile]) -> None:
    if not files:
        raise HTTPException(400, "Select at least one document")
    if len(files) > MAX_BATCH_FILES:
        raise HTTPException(400, f"Upload no more than {MAX_BATCH_FILES} documents at once")


async def prepare_upload(file: UploadFile):
    filename, content_type, data = await read_upload(file)
    try:
        return await prepare_document_bytes(filename, content_type, data)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    except Exception as error:
        raise HTTPException(503, "Document indexing service is unavailable") from error


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...), user_id: int = Form(gt=0)
) -> dict[str, object]:
    stored = await store_documents([await prepare_upload(file)], user_id)
    return stored[0]


@router.post("/batch", status_code=status.HTTP_201_CREATED)
async def upload_document_batch(
    files: list[UploadFile] = File(...),
    user_id: int = Form(gt=0),
) -> dict[str, object]:
    validate_batch(files)
    stored = await store_documents(
        [await prepare_upload(file) for file in files], user_id
    )
    return summarize_upload(stored)


@router.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def queue_document_batch(
    files: list[UploadFile] = File(...), user_id: int = Form(gt=0)
) -> dict[str, object]:
    validate_batch(files)
    uploads = [await read_upload(file) for file in files]
    database = get_pool()
    job_dir: Path | None = None

    try:
        async with database.acquire() as connection, connection.transaction():
            job_id = await connection.fetchval(
                "INSERT INTO ingestion_jobs(total_files, user_id) VALUES($1, $2) RETURNING id",
                len(uploads),
                user_id,
            )
            job_dir = Path(settings.upload_dir) / str(job_id)
            job_dir.mkdir(parents=True, exist_ok=True)
            job_dir.chmod(0o777)

            for filename, content_type, data in uploads:
                storage_path = job_dir / f"{uuid4().hex}-{filename}"
                storage_path.write_bytes(data)
                storage_path.chmod(0o666)
                await connection.execute(
                    """
                    INSERT INTO ingestion_job_files(
                        job_id, filename, content_type, storage_path
                    ) VALUES($1, $2, $3, $4)
                    """,
                    job_id,
                    filename,
                    content_type,
                    str(storage_path),
                )
    except Exception:
        if job_dir is not None:
            rmtree(job_dir, ignore_errors=True)
        raise

    try:
        process_ingestion_job.delay(job_id)
    except Exception as error:
        await database.execute(
            """
            UPDATE ingestion_jobs
            SET status = 'failed', error = $2, updated_at = NOW()
            WHERE id = $1
            """,
            job_id,
            "Could not enqueue the ingestion job",
        )
        raise HTTPException(503, "Background worker queue is unavailable") from error

    return {"job_id": job_id, "status": "queued", "total_files": len(uploads)}


@router.get("/jobs/{job_id}")
async def get_ingestion_job(
    job_id: int, user_id: int = Query(gt=0)
) -> dict[str, object]:
    job = await get_pool().fetchrow(
        """
        SELECT id, status, total_files, processed_files, duplicate_files,
               attempts, error, created_at, updated_at
        FROM ingestion_jobs
        WHERE id = $1 AND user_id = $2
        """,
        job_id,
        user_id,
    )
    if job is None:
        raise HTTPException(404, "Ingestion job not found")

    files = await get_pool().fetch(
        """
        SELECT id, filename, status, document_id, duplicate, error
        FROM ingestion_job_files
        WHERE job_id = $1
        ORDER BY id
        """,
        job_id,
    )
    return {**dict(job), "files": [dict(file) for file in files]}


@router.get("")
async def list_documents(user_id: int = Query(gt=0)) -> list[dict[str, object]]:
    rows = await get_pool().fetch(
        """
        SELECT d.id, d.filename, d.content_type, d.created_at,
               COUNT(c.id)::int AS chunks
        FROM documents d
        LEFT JOIN document_chunks c ON c.document_id = d.id
        WHERE d.user_id = $1
        GROUP BY d.id
        ORDER BY d.created_at DESC
        """,
        user_id,
    )
    return [dict(row) for row in rows]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: int, user_id: int = Query(gt=0)
) -> None:
    result = await get_pool().execute(
        "DELETE FROM documents WHERE id = $1 AND user_id = $2", document_id, user_id
    )
    if result == "DELETE 0":
        raise HTTPException(404, "Document not found")


def summarize_upload(stored: list[dict[str, object]]) -> dict[str, object]:
    return {
        "documents": stored,
        "total_files": len(stored),
        "indexed_documents": sum(not bool(document["duplicate"]) for document in stored),
        "duplicate_documents": sum(bool(document["duplicate"]) for document in stored),
        "total_chunks": sum(
            int(document["chunks"])
            for document in stored
            if not bool(document["duplicate"])
        ),
    }
