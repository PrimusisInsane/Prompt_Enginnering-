import re
from google import genai
from app.config import settings
from app.services.prompts import BARK_SYSTEM_PROMPT

client = genai.Client(api_key=settings.gemini_api_key)


def _strip_markdown_fences(text: str) -> str:
    """
    Gemini sometimes wraps JSON output in ```json ... ``` fences despite
    instructions not to. This strips them so downstream json.loads() works.
    """
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


async def call_llm(prompt: str, force_bad: bool = False) -> str:
    full_prompt = f"{BARK_SYSTEM_PROMPT}\n\n{prompt}"

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=full_prompt,
    )

    return _strip_markdown_fences(response.text)