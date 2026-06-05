<<<<<<< HEAD
﻿from pydantic_settings import BaseSettings


class Settings(BaseSettings):
=======
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

>>>>>>> 7c418751c71fd61627f81bd3fe4fb9a2a46d8869
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    UPLOAD_DIR: str = "/tmp/sori-yaho/uploads"
    MAX_FILE_SIZE_MB: int = 50

<<<<<<< HEAD
    class Config:
        env_file = ".env"
=======
    # 피아노 채보 모델: "piano_transcription" | "basic_pitch"
    TRANSCRIPTION_MODEL: str = "piano_transcription"

    # MuseScore 폴리싱
    MUSESCORE_PATH: str = ""
    MUSESCORE_POLISH_ENABLED: bool = True
>>>>>>> 7c418751c71fd61627f81bd3fe4fb9a2a46d8869


settings = Settings()
