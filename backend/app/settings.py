from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        env_file_encoding="utf-8",
    )

    TUSHARE_TOKEN: str
    DATABASE_URL: str
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000


settings = Settings()
