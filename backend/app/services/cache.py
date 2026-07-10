import hashlib
import json

import redis.asyncio as redis

from app.config import get_settings
from app.schemas import SearchResult

settings = get_settings()


def retrieval_cache_key(
    query: str,
    limit: int,
    user_id: int,
    document_ids: list[int] | None,
) -> str:
    payload = json.dumps(
        {
            "query": query.strip().lower(),
            "limit": limit,
            "user_id": user_id,
            "document_ids": sorted(document_ids or []),
        },
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"retrieval:search:{digest}"


def redis_client():
    return redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
    )


async def get_cached_search_results(cache_key: str) -> list[SearchResult] | None:
    client = redis_client()
    try:
        cached = await client.get(cache_key)
        if not cached:
            await client.incr("metrics:retrieval_cache_misses")
            return None
        await client.incr("metrics:retrieval_cache_hits")
        return [SearchResult(**item) for item in json.loads(cached)]
    except Exception:
        return None
    finally:
        await client.aclose()


async def set_cached_search_results(cache_key: str, results: list[SearchResult]) -> None:
    client = redis_client()
    try:
        await client.setex(
            cache_key,
            settings.retrieval_cache_ttl_seconds,
            json.dumps([result.model_dump() for result in results]),
        )
    except Exception:
        return
    finally:
        await client.aclose()


async def get_cache_metrics() -> dict[str, int | float]:
    client = redis_client()
    try:
        hits, misses = await client.mget(
            "metrics:retrieval_cache_hits",
            "metrics:retrieval_cache_misses",
        )
        hit_count = int(hits or 0)
        miss_count = int(misses or 0)
        total = hit_count + miss_count
        return {
            "hits": hit_count,
            "misses": miss_count,
            "hit_rate": round(hit_count / total, 4) if total else 0.0,
            "ttl_seconds": settings.retrieval_cache_ttl_seconds,
        }
    except Exception:
        return {
            "hits": 0,
            "misses": 0,
            "hit_rate": 0.0,
            "ttl_seconds": settings.retrieval_cache_ttl_seconds,
        }
    finally:
        await client.aclose()
