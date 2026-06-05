from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    UPLOAD_DIR: str = "/tmp/sori-yaho/uploads"
    OUTPUT_DIR: str = "/tmp/sori-yaho/outputs"
    MAX_FILE_SIZE_MB: int = 50

    # 피아노 채보 모델: "piano_transcription" | "basic_pitch"
    TRANSCRIPTION_MODEL: str = "basic_pitch"

    # MuseScore 폴리싱
    MUSESCORE_PATH: str = ""
    MUSESCORE_POLISH_ENABLED: bool = True


settings = Settings()
