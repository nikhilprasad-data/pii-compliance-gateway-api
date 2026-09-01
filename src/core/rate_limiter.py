from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis
from src.core.cache import get_redis

RATE_LIMIT = 50
RATE_LIMIT_WINDOW_SECONDS = 60

RATE_LIMIT_SCRIPT = """
local current_count = redis.call("INCR", KEYS[1])

if current_count == 1 then
    redis.call("EXPIRE", KEYS[1], ARGV[1])
end

return current_count
"""


async def check_rate_limit(request: Request,redis_client: Redis = Depends(get_redis)) -> None:
    """
    Enforce a per-IP request limit using Redis.
    Each client IP is allowed a maximum of 50 requests
    within a 60-second window.
    """

    client_ip = request.client.host

    redis_key = f"rate_limit:{client_ip}"

    current_count = await redis_client.eval(
        RATE_LIMIT_SCRIPT,
        1,
        redis_key,
        RATE_LIMIT_WINDOW_SECONDS,
    )

    if current_count > RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Try again later.",
            headers={"Retry-After": str(RATE_LIMIT_WINDOW_SECONDS)},
        )
