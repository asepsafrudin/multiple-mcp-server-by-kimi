"""Centralised, environment-driven settings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime settings are loaded from environment / .env.

    Never put real secrets in code; use the `.env` file (gitignored).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core
    mcp_root: Path = Path("/home/aseps/MCP")
    log_level: str = "INFO"
    allowed_directories: list[str] = ["/home/aseps/MCP", "/home/aseps/Workspace", "/tmp"]
    max_file_size_mb: int = 10

    # PostgreSQL + pgvector
    db_url: str = ""
    db_pool_min: int = 1
    db_pool_max: int = 10

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Ollama
    ollama_url: str = "http://localhost:11434"
    ollama_embedding_model: str = "nomic-embed-text"
    ollama_embedding_dimension: int = 768
    ollama_chat_model: str = "llama3.2"

    # Rust filesystem bridge
    rust_fs_binary: Path = Path("/home/aseps/MCP/bin/rust-mcp-filesystem")

    # Optional integrations
    gmail_credentials_path: Path | None = None
    gmail_token_path: Path | None = None
    google_vision_credentials_path: Path | None = None
    gemini_api_key: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # SQLite memory & knowledge (local-first default)
    memory_db_path: Path = Path("/home/aseps/MCP/data/memory_v2.db")
    knowledge_db_path: Path = Path("/home/aseps/MCP/data/knowledge_v2.db")

    # Workspace knowledge
    workspace_root: Path = Path("/home/aseps/Workspace")
    knowledge_max_files_per_run: int = 200


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
