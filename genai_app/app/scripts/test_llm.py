import asyncio
from app.services.generation import get_validated_bark
from app.services.storage import save_bark_generation
from app.db import async_session


async def main():
    prompt_input = "Generate bark lines for enemy_type: regular_zombie."

    validated = await get_validated_bark(prompt_input)

    print("\n--- Validated after retry ---")
    print(validated)

    async with async_session() as session:
        record = await save_bark_generation(session, prompt_input, validated)

    print("\n--- Saved to Postgres ---")
    print("id:", record.id)


if __name__ == "__main__":
    asyncio.run(main())