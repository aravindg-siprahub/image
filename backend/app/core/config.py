from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Image Curation Platform"
    CORS_ORIGINS: str = "http://localhost:3000"
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
    SIMILARITY_THRESHOLD: float = 0.95  # pHash+color combined similarity threshold

    # Two-stage quality decision thresholds:
    #   QUALITY_THRESHOLD: images at or above this are always kept
    #   QUALITY_FLOOR:     images below this are always rejected (clearly unusable)
    #   Between floor and threshold: the relative winner of each similarity group is kept
    #
    # Camera photos (real indoor/group shots) typically score 38-75 on our log-scale
    # sharpness pipeline. We keep any photo that is the best of its scene.
    # Only true corruption/heavy blur/black frames fall below QUALITY_FLOOR=25.
    QUALITY_THRESHOLD: float = 38.0
    QUALITY_FLOOR: float = 25.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8')

settings = Settings()