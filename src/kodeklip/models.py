"""
Database models for KodeKlip using SQLModel.

This module defines the core database models for repository management
and search indexing.
Uses SQLModel for type-safe ORM with SQLite backend.
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


class Repository(SQLModel, table=True):
    """
    Repository model representing a cloned git repository.

    Stores information about managed repositories including their
    local paths, indexing status, and last update timestamps.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    alias: str = Field(
        index=True, unique=True, description="Unique identifier for the repository"
    )
    url: str = Field(description="Git repository URL")
    local_path: str = Field(
        description="Local filesystem path where repository is cloned"
    )
    last_updated: Optional[datetime] = Field(
        default=None, description="Timestamp of last repository update"
    )
    indexed: bool = Field(
        default=False,
        description="Whether repository has been indexed for semantic search",
    )

    # Relationship: One repository can have many search index entries
    search_indexes: list["SearchIndex"] = Relationship(back_populates="repository")


class SearchIndex(SQLModel, table=True):
    """
    Search index model for storing parsed code chunks and embeddings.

    Each entry represents a searchable code chunk from a repository file,
    with optional embedding data for semantic search capabilities.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    repo_id: int = Field(
        foreign_key="repository.id", description="Reference to parent repository"
    )
    file_path: str = Field(
        index=True, description="Relative path to file within repository"
    )
    content_hash: str = Field(
        index=True, description="Hash of file content for change detection"
    )
    embedding_data: Optional[str] = Field(
        default=None, description="JSON-serialized embedding vector data"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when index entry was created",
    )

    # Relationship: Each search index entry belongs to one repository
    repository: Optional[Repository] = Relationship(back_populates="search_indexes")
