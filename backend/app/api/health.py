import asyncio

import asyncpg
import httpx
import redis.asyncio as redis
from fastapi import APIRouter

from app.config import get_settings
from app.services.cache import get_cache_metrics

router = APIRouter(prefix="/api", tags=["health"])
settings = get_settings()


async def check_postgres() -> bool:
    connection = None
    try:
        connection = await asyncpg.connect(settings.database_url, timeout=2)
        return await connection.fetchval("SELECT 1") == 1
    except Exception:
        return False
    finally:
        if connection is not None:
            await connection.close()


async def check_redis() -> bool:
    client = redis.from_url(settings.redis_url, socket_connect_timeout=2)
    try:
        return bool(await client.ping())
    except Exception:
        return False
    finally:
        await client.aclose()


async def check_ollama() -> bool:
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            response = await client.get(f"{settings.ollama_url}/api/tags")
            return response.is_success
    except Exception:
        return False


@router.get("/health")
async def health() -> dict[str, object]:
    postgres_ok, redis_ok, ollama_ok = await asyncio.gather(
        check_postgres(), check_redis(), check_ollama()
    )
    components = {
        "api": True,
        "postgres": postgres_ok,
        "redis": redis_ok,
        "ollama": ollama_ok,
    }
    return {
        "status": "healthy" if all(components.values()) else "degraded",
        "components": components,
    }


@router.get("/metrics/cache")
async def cache_metrics() -> dict[str, int | float]:
    return await get_cache_metrics()
