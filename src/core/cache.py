import redis.asyncio as redis
from src.config import settings


redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    password=settings.REDIS_PASSWORD,
    db=settings.REDIS_DB,
    ssl=settings.REDIS_SSL,
    decode_responses=True,
)


async def get_redis():
    yield redis_client