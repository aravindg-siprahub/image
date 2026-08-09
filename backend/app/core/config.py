from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Image Curation Platform"
    DATABASE_URL: str
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_STORAGE_BUCKET: str = "imageupload"
    OPENAI_API_KEY: str | None = None
    VISION_MODEL: str = "gpt-4o-mini"
    MAX_CONCURRENCY: int = 8
    SIMILARITY_THRESHOLD: float = 0.90  # pHash+color combined similarity threshold

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8')

settings = Settings()
