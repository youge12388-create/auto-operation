from __future__ import annotations

from redis import Redis
from redis.exceptions import RedisError

from .settings import get_settings

JOB_QUEUE = "content_ops:jobs"


def redis_client() -> Redis:
    return Redis.from_url(
        get_settings().redis_url,
        decode_responses=True,
        socket_connect_timeout=0.2,
        socket_timeout=0.2,
    )


def wake_job(job_id: str) -> bool:
    client = redis_client()
    try:
        client.rpush(JOB_QUEUE, job_id)
        return True
    except RedisError:
        return False
    finally:
        client.close()