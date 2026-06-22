from dataclasses import dataclass

from app.database import get_pool
from app.services.documents import chunk_text, extract_text, hash_chunks
from app.services.ollama import create_embeddings


@dataclass
class PreparedDocument:
    filename: str
    content_type: str
    content_hash: str
    chunks: list[str]
    embeddings: list[list[float]]


async def prepare_document_bytes(
    filename: str, content_type: str, data: bytes
) -> PreparedDocument:
    text = extract_text(filename, data)
    chunks = chunk_text(text)
    if not chunks:
        raise ValueError(f"{filename}: document contains no readable text")

    embeddings = await create_embeddings(chunks)
    return PreparedDocument(
        filename=filename,
        content_type=content_type,
        content_hash=hash_chunks(chunks),
        chunks=chunks,
        embeddings=embeddings,
    )


async def store_documents(
    documents: list[PreparedDocument], user_id: int
) -> list[dict[str, object]]:
    stored: list[dict[str, object]] = []
    database = get_pool()
    async with database.acquire() as connection, connection.transaction():
        for document in documents:
            existing = await connection.fetchrow(
                """
                SELECT d.id, COUNT(c.id)::int AS chunks
                FROM documents d
                LEFT JOIN document_chunks c ON c.document_id = d.id
                WHERE d.content_hash = $1 AND d.user_id = $2
                GROUP BY d.id
                """,
                document.content_hash,
                user_id,
            )
            if existing is not None:
                stored.append(
                    {
                        "id": existing["id"],
                        "filename": document.filename,
                        "chunks": existing["chunks"],
                        "duplicate": True,
                    }
                )
                continue

            document_id = await connection.fetchval(
                """
                INSERT INTO documents(filename, content_type, content_hash, user_id)
                VALUES($1, $2, $3, $4)
                RETURNING id
                """,
                document.filename,
                document.content_type,
                document.content_hash,
                user_id,
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
                    "duplicate": False,
                }
            )
    return stored
