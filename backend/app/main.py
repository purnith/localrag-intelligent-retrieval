from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agent import router as agent_router
from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.api.context import router as context_router
from app.api.health import router as health_router
from app.api.retrieval import router as retrieval_router
from app.config import get_settings
from app.database import close_database, initialize_database

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await initialize_database()
    yield
    await close_database()

app = FastAPI(
    title=settings.app_name,
    description="A retrieval-augmented generation platform for multi-document search and source-grounded answers.",
    version="0.5.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(context_router)
app.include_router(agent_router)
app.include_router(documents_router)
app.include_router(retrieval_router)


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {"message": settings.app_name, "docs": "/docs"}
