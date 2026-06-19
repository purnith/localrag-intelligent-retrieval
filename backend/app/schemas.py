from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    limit: int = Field(default=5, ge=1, le=10)


class SearchResult(BaseModel):
    chunk_id: int
    document_id: int
    filename: str
    content: str
    score: float


class AskResponse(BaseModel):
    answer: str
    sources: list[SearchResult]
