"""Redis queue operations for document ingestion."""

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings


class IngestQueue:
    """Add document ingestion items to the ARQ Redis queue."""

    def __init__(self, redis: ArqRedis) -> None:
        self.redis = redis

    @classmethod
    async def connect(cls, redis_url: str) -> "IngestQueue":
        """Create a connection to Redis."""
        settings = RedisSettings.from_dsn(redis_url)
        redis = await create_pool(settings)
        return cls(redis)

    async def put(self, item_ids: list[int]) -> None:
        """Queue each ingestion item as a separate worker job."""
        for item_id in item_ids:
            await self.redis.enqueue_job(
                "ingest_document",
                item_id,
                _job_id=f"ingest-{item_id}",
            )

    async def close(self) -> None:
        """Close the Redis connection."""
        await self.redis.aclose()
