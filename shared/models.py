"""Common Pydantic models for memory, knowledge, and skills."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class MemoryEntry(BaseModel):
    """A single long-term memory record."""

    namespace: str = Field(..., min_length=1)
    id: str = ""
    content: str = Field(..., min_length=1)
    summary: str | None = None
    category: str = "general"
    tags: list[str] = Field(default_factory=list)
    importance: int = Field(default=5, ge=1, le=10)
    access_count: int = 0
    quant_level: str = "raw"
    memory_type: str = "semantic"
    validation_status: str = "pending"
    source_task_id: str | None = None
    is_archived: bool = False
    source: str | None = None
    project: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None

    @field_validator("category")
    @classmethod
    def _valid_category(cls, v: str) -> str:
        allowed = {"general", "decision", "learning", "context", "error", "pattern"}
        if v not in allowed:
            raise ValueError(f"category must be one of {allowed}")
        return v

    @field_validator("validation_status")
    @classmethod
    def _valid_status(cls, v: str) -> str:
        allowed = {"pending", "verified", "rejected"}
        if v not in allowed:
            raise ValueError(f"validation_status must be one of {allowed}")
        return v

    def to_compact(self) -> dict[str, Any]:
        """Token-efficient representation for LLM consumption."""
        return {
            "id": self.id,
            "namespace": self.namespace,
            "category": self.category,
            "memory_type": self.memory_type,
            "validation_status": self.validation_status,
            "is_archived": self.is_archived,
            "content": self.summary if self.summary else self.content[:300],
            "tags": self.tags,
            "importance": self.importance,
            "project": self.project,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class KnowledgeChunk(BaseModel):
    """A chunk of harvested workspace knowledge."""

    id: str | None = None
    file_path: str
    file_hash: str
    file_type: str
    project: str
    chunk_index: int = 0
    total_chunks: int = 1
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class Skill(BaseModel):
    """A procedural memory / skill entry."""

    id: str = ""
    name: str = Field(..., min_length=1)
    namespace: str = "global"
    category: str = "general"
    description: str
    triggers: list[str] = Field(default_factory=list)
    prompt_template: str
    tools_required: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    version: int = 1
    embedding: list[float] | None = None
