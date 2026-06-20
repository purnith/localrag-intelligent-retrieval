from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.database import get_pool
from app.services.documents import chunk_text, extract_text
from app.services.ollama import create_embeddings

router = APIRouter(prefix="/api/documents", tags=["documents"])
MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_BATCH_FILES = 10
SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt"}


@dataclass
class PreparedDocument:
    filename: str
    content_type: str
    chunks: list[str]
    embeddings: list[list[float]]


async def prepare_document(file: UploadFile) -> PreparedDocument:
    filename = Path(file.filename or "document").name
    if Path(filename).suffix.lower() not in SUPPORTED_SUFFIXES:
        raise HTTPException(
            400, f"{filename}: supported file types are PDF, DOCX, and TXT"
        )

    data = await file.read(MAX_FILE_SIZE + 1)
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(413, f"{filename}: file must be 10 MB or smaller")

    try:
        text = extract_text(filename, data)
    except Exception as error:
        raise HTTPException(400, f"{filename}: could not read document: {error}") from error

    chunks = chunk_text(text)
    if not chunks:
        raise HTTPException(400, f"{filename}: document contains no readable text")

    try:
        embeddings = await create_embeddings(chunks)
    except Exception as error:
        raise HTTPException(503, "The local embedding model is unavailable") from error

    return PreparedDocument(
        filename=filename,
        content_type=file.content_type or "application/octet-stream",
        chunks=chunks,
        embeddings=embeddings,
    )


async def store_documents(
    documents: list[PreparedDocument],
) -> list[dict[str, object]]:
    stored: list[dict[str, object]] = []
    database = get_pool()
    async with database.acquire() as connection, connection.transaction():
        for document in documents:
            document_id = await connection.fetchval(
                """
                INSERT INTO documents(filename, content_type)
                VALUES($1, $2)
                RETURNING id
                """,
                document.filename,
                document.content_type,
            )
            await connection.executemany(
                """
                INSERT INTO document_chunks(document_id, chunk_index, content, embedding)
                VALUES($1, $2, $3, $4::vector)
                """,
                [
                    (document_id, index, chunk, str(embedding))
                    for index, (chunk, embedding) in enumerate(
                        zip(document.chunks, document.embeddings)
                    )
                ],
            )
            stored.append(
                {
                    "id": document_id,
                    "filename": document.filename,
                    "chunks": len(document.chunks),
                }
            )
    return stored


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_document(file: UploadFile = File(...)) -> dict[str, object]:
    stored = await store_documents([await prepare_document(file)])
    return stored[0]


@router.post("/batch", status_code=status.HTTP_201_CREATED)
async def upload_document_batch(
    files: list[UploadFile] = File(...),
) -> dict[str, object]:
    if not files:
        raise HTTPException(400, "Select at least one document")
    if len(files) > MAX_BATCH_FILES:
        raise HTTPException(400, f"Upload no more than {MAX_BATCH_FILES} documents at once")

    prepared = [await prepare_document(file) for file in files]
    stored = await store_documents(prepared)
    return {
        "documents": stored,
        "total_documents": len(stored),
        "total_chunks": sum(int(document["chunks"]) for document in stored),
    }


@router.get("")
async def list_documents() -> list[dict[str, object]]:
    rows = await get_pool().fetch(
        """
        SELECT d.id, d.filename, d.content_type, d.created_at,
               COUNT(c.id)::int AS chunks
        FROM documents d
        LEFT JOIN document_chunks c ON c.document_id = d.id
        GROUP BY d.id
        ORDER BY d.created_at DESC
        """
    )
    return [dict(row) for row in rows]
