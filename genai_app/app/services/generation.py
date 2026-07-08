import json
from pydantic import ValidationError
from redis.asyncio import Redis
from app.services.llm_client import call_llm
from app.schemas import BarkResponse
from app.config import settings

redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


async def get_validated_bark(prompt: str, force_bad_first_try: bool = False) -> BarkResponse:
    raw = await call_llm(prompt, force_bad=force_bad_first_try)

    try:
        parsed = json.loads(raw)
        return BarkResponse.model_validate(parsed)
    except (json.JSONDecodeError, ValidationError) as e:
        print(f"First attempt failed validation: {e}")
        print("Retrying...")
        raw_retry = await call_llm(prompt, force_bad=False)
        parsed_retry = json.loads(raw_retry)
        return BarkResponse.model_validate(parsed_retry)

async def get_cached_or_generate_bark(enemy_type: str, prompt: str) -> tuple[BarkResponse, bool]:
    """
    Checks Redis for a cached bark response for this enemy_type first.
    Returns (validated_response, was_cached).
    """
    cache_key = f"bark:{enemy_type}"

    cached = await redis_client.get(cache_key)
    if cached:
        return BarkResponse.model_validate(json.loads(cached)), True

    validated = await get_validated_bark(prompt)
    await redis_client.set(cache_key, validated.model_dump_json(), ex=3600)  # cache 1 hour
    return validated, False