from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Generation
from app.schemas import BarkResponse


async def save_bark_generation(
    session: AsyncSession,
    prompt_input: str,
    validated: BarkResponse,
) -> Generation:
    record = Generation(
        content_type=validated.content_type,
        prompt_input=prompt_input,
        generated_output=validated.model_dump_json(),
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record