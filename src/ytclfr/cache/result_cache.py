import json
import logging
from uuid import UUID

import redis

from ytclfr.core.config import get_settings

logger = logging.getLogger(__name__)

_redis_client: redis.Redis | None = None
RESULT_CACHE_KEY_PREFIX = "ytclfr:job"

def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client

def get_cached_result(job_id: UUID) -> dict | None:
    try:
        client = _get_redis()
        key = f"{RESULT_CACHE_KEY_PREFIX}:{job_id}:result"
        data = client.get(key)
        if data:
            return json.loads(data)
    except Exception as e:
        logger.warning(f"Redis get_cached_result failed: {e}")
    return None

def cache_result(job_id: UUID, result: dict, ttl_seconds: int) -> None:
    try:
        client = _get_redis()
        key = f"{RESULT_CACHE_KEY_PREFIX}:{job_id}:result"
        client.set(key, json.dumps(result), ex=ttl_seconds)
    except Exception as e:
        logger.warning(f"Redis cache_result failed: {e}")

def invalidate_result(job_id: UUID) -> None:
    try:
        client = _get_redis()
        key = f"{RESULT_CACHE_KEY_PREFIX}:{job_id}:result"
        client.delete(key)
    except Exception as e:
        logger.warning(f"Redis invalidate_result failed: {e}")
