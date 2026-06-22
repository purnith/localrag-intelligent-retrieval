from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    user_id: int = Field(gt=0)
    conversation_id: int | None = Field(default=None, gt=0)
    limit: int = Field(default=5, ge=1, le=10)
    document_ids: list[int] | None = Field(default=None, max_length=50)


class SearchResult(BaseModel):
    chunk_id: int
    document_id: int
    filename: str
    content: str
    score: float


class AskResponse(BaseModel):
    answer: str
    sources: list[SearchResult]
    conversation_id: int


class UserCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)


class AgentResponse(AskResponse):
    action: str
    tool_trace: list[str]
