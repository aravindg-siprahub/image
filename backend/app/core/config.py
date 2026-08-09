from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Image Curation Platform"
    DATABASE_URL: str
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_STORAGE_BUCKET: str = "imageupload"
    GROQ_API_KEY: str | None = None
    GROQ_API_KEY_2: str | None = None
    GROQ_VISION_MODEL: str = "qwen/qwen3.6-27b"
    GROQ_MAX_CONCURRENCY: int = 8
    # Soft daily token budget (matches free-tier TPD). Skip Groq when remaining is too low.
    GROQ_DAILY_TOKEN_BUDGET: int = 200000
    GROQ_TOKEN_RESERVE_PER_IMAGE: int = 4000
    SIMILARITY_THRESHOLD: float = 0.90  # pHash+color combined similarity threshold

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8')

settings = Settings()
