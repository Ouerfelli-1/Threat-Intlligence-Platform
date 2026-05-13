import json
from typing import Any

from redis.asyncio import Redis, from_url


class Cache:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    @classmethod
    def from_url(cls, url: str) -> "Cache":
        return cls(from_url(url, encoding="utf-8", decode_responses=True))

    @property
    def redis(self) -> Redis:
        return self._redis

    async def close(self) -> None:
        await self._redis.aclose()

    async def get_json(self, key: str) -> Any | None:
        raw = await self._redis.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        await self._redis.set(key, json.dumps(value, default=str), ex=ttl_seconds)

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)

    async def incr_with_ttl(self, key: str, ttl_seconds: int) -> int:
        pipe = self._redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, ttl_seconds, nx=True)
        results = await pipe.execute()
        return int(results[0])


__all__ = ["Cache"]
