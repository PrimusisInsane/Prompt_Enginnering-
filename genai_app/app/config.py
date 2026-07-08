from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    
    gemini_api_key: str = ""  # no longer required, keep optional
    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/genai_app"
    redis_url: str = "redis://localhost:6379"

    class Config:
        env_file = ".env"

settings = Settings()