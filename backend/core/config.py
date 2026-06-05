from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    UPLOAD_DIR: str = "/tmp/sori-yaho/uploads"
    MAX_FILE_SIZE_MB: int = 50

    class Config:
        env_file = ".env"


settings = Settings()
