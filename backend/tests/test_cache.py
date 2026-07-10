from app.services.cache import get_cache_metrics, retrieval_cache_key


def test_retrieval_cache_key_is_user_and_document_scoped() -> None:
    first = retrieval_cache_key("Vacation policy", 5, 1, [3, 2])
    same_documents_different_order = retrieval_cache_key(" vacation policy ", 5, 1, [2, 3])
    different_user = retrieval_cache_key("Vacation policy", 5, 2, [2, 3])

    assert first == same_documents_different_order
    assert first != different_user


def test_cache_metrics_falls_back_when_redis_unavailable() -> None:
    import asyncio

    metrics = asyncio.run(get_cache_metrics())
    assert {"hits", "misses", "hit_rate", "ttl_seconds"} <= metrics.keys()

