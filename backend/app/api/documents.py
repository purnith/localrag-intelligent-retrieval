from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.database import get_pool
from app.services.documents import chunk_text, extract_text
from app.services.ollama import create_embeddings

router = APIRouter(prefix="/api/documents", tags=["documents"])
MAX_FILE_SIZE = 10 * 1024 * 1024
SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt"}


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_document(file: UploadFile = File(...)) -> dict[str, object]:
    filename = Path(file.filename or "document").name
    if Path(filename).suffix.lower() not in SUPPORTED_SUFFIXES:
        raise HTTPException(400, "Supported file types are PDF, DOCX, and TXT")

    data = await file.read(MAX_FILE_SIZE + 1)
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(413, "File must be 10 MB or smaller")

    try:
        text = extract_text(filename, data)
    except Exception as error:
        raise HTTPException(400, f"Could not read document: {error}") from error

    chunks = chunk_text(text)
    if not chunks:
        raise HTTPException(400, "The document contains no readable text")

    try:
        embeddings = await create_embeddings(chunks)
    except Exception as error:
        raise HTTPException(503, "The local embedding model is unavailable") from error

    database = get_pool()
    async with database.acquire() as connection, connection.transaction():
        document_id = await connection.fetchval(
            "INSERT INTO documents(filename, content_type) VALUES($1, $2) RETURNING id",
            filename,
            file.content_type or "application/octet-stream",
        )
        await connection.executemany(
            """
            INSERT INTO document_chunks(document_id, chunk_index, content, embedding)
            VALUES($1, $2, $3, $4::vector)
            """,
            [
                (document_id, index, chunk, str(embedding))
                for index, (chunk, embedding) in enumerate(zip(chunks, embeddings))
            ],
        )

    return {"id": document_id, "filename": filename, "chunks": len(chunks)}


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
