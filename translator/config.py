from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5-coder:7b"
    ollama_translation_model: str | None = None
    ollama_fix_model: str | None = None
    ollama_review_model: str | None = None
    ollama_assistant_model: str | None = None
    ollama_codegen_model: str | None = None
    ollama_project_model: str | None = None
    ollama_timeout_seconds: int = 180
    use_ollama: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
