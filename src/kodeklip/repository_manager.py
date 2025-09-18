"""
Repository CRUD operations and management.

This module provides high-level functions for managing repositories in the database,
including adding, retrieving, updating, and removing repository records.
"""

from datetime import datetime

from sqlmodel import select

from .database import get_session
from .models import Repository, SearchIndex


class RepositoryError(Exception):
    """Base exception for repository operations."""

    pass


class RepositoryNotFoundError(RepositoryError):
    """Raised when a repository is not found."""

    pass


class RepositoryAlreadyExistsError(RepositoryError):
    """Raised when trying to add a repository that already exists."""

    pass


def add_repository(
    alias: str, url: str, local_path: str, db_path: str | None = None
) -> Repository:
    """Add a new repository to the database.

    Args:
        alias: Unique identifier for the repository
        url: Git repository URL
        local_path: Local filesystem path where repository is cloned
        db_path: Optional custom database path

    Returns:
        Created Repository instance

    Raises:
        RepositoryAlreadyExistsError: If repository with alias already exists
        RepositoryError: If database operation fails
    """
    try:
        with get_session(db_path) as session:
            # Check if repository already exists
            statement = select(Repository).where(Repository.alias == alias)
            existing = session.exec(statement).first()

            if existing is not None:
                raise RepositoryAlreadyExistsError(
                    f"Repository with alias '{alias}' already exists"
                )

            # Create new repository
            repository = Repository(
                alias=alias,
                url=url,
                local_path=local_path,
                last_updated=None,
                indexed=False,
            )

            session.add(repository)
            session.commit()
            session.refresh(repository)

            return repository

    except RepositoryAlreadyExistsError:
        raise
    except Exception as e:
        raise RepositoryError(f"Failed to add repository '{alias}': {str(e)}") from e


def get_repository(alias: str, db_path: str | None = None) -> Repository:
    """Get repository by alias.

    Args:
        alias: Repository alias to look up
        db_path: Optional custom database path

    Returns:
        Repository instance

    Raises:
        RepositoryNotFoundError: If repository is not found
        RepositoryError: If database operation fails
    """
    try:
        with get_session(db_path) as session:
            statement = select(Repository).where(Repository.alias == alias)
            repository = session.exec(statement).first()

            if repository is None:
                raise RepositoryNotFoundError(
                    f"Repository with alias '{alias}' not found"
                )

            return repository

    except RepositoryNotFoundError:
        raise
    except Exception as e:
        raise RepositoryError(f"Failed to get repository '{alias}': {str(e)}") from e


def list_repositories(db_path: str | None = None) -> list[Repository]:
    """List all repositories.

    Args:
        db_path: Optional custom database path

    Returns:
        List of Repository instances, ordered by alias

    Raises:
        RepositoryError: If database operation fails
    """
    try:
        with get_session(db_path) as session:
            statement = select(Repository).order_by(Repository.alias)
            repositories = session.exec(statement).all()
            return list(repositories)

    except Exception as e:
        raise RepositoryError(f"Failed to list repositories: {str(e)}") from e


def update_repository_status(
    alias: str,
    last_updated: datetime | None = None,
    indexed: bool | None = None,
    db_path: str | None = None,
) -> Repository:
    """Update repository status information.

    Args:
        alias: Repository alias to update
        last_updated: Optional new last_updated timestamp
        indexed: Optional new indexed status
        db_path: Optional custom database path

    Returns:
        Updated Repository instance

    Raises:
        RepositoryNotFoundError: If repository is not found
        RepositoryError: If database operation fails
    """
    try:
        with get_session(db_path) as session:
            statement = select(Repository).where(Repository.alias == alias)
            repository = session.exec(statement).first()

            if repository is None:
                raise RepositoryNotFoundError(
                    f"Repository with alias '{alias}' not found"
                )

            # Update fields if provided
            if last_updated is not None:
                repository.last_updated = last_updated

            if indexed is not None:
                repository.indexed = indexed

            session.add(repository)
            session.commit()
            session.refresh(repository)

            return repository

    except RepositoryNotFoundError:
        raise
    except Exception as e:
        raise RepositoryError(f"Failed to update repository '{alias}': {str(e)}") from e


def remove_repository(alias: str, db_path: str | None = None) -> bool:
    """Remove repository and all associated search indexes.

    Args:
        alias: Repository alias to remove
        db_path: Optional custom database path

    Returns:
        True if repository was removed, False if it didn't exist

    Raises:
        RepositoryError: If database operation fails
    """
    try:
        with get_session(db_path) as session:
            # Get repository
            statement = select(Repository).where(Repository.alias == alias)
            repository = session.exec(statement).first()

            if repository is None:
                return False

            # Remove all associated search indexes first (due to foreign key constraint)
            search_index_statement = select(SearchIndex).where(
                SearchIndex.repo_id == repository.id
            )
            search_indexes = session.exec(search_index_statement).all()

            for search_index in search_indexes:
                session.delete(search_index)

            # Remove repository
            session.delete(repository)
            session.commit()

            return True

    except Exception as e:
        raise RepositoryError(f"Failed to remove repository '{alias}': {str(e)}") from e


def repository_exists(alias: str, db_path: str | None = None) -> bool:
    """Check if repository exists.

    Args:
        alias: Repository alias to check
        db_path: Optional custom database path

    Returns:
        True if repository exists, False otherwise

    Raises:
        RepositoryError: If database operation fails
    """
    try:
        with get_session(db_path) as session:
            statement = select(Repository).where(Repository.alias == alias)
            repository = session.exec(statement).first()
            return repository is not None

    except Exception as e:
        raise RepositoryError(
            f"Failed to check if repository '{alias}' exists: {str(e)}"
        ) from e


def get_repository_count(db_path: str | None = None) -> int:
    """Get total count of repositories.

    Args:
        db_path: Optional custom database path

    Returns:
        Number of repositories in database

    Raises:
        RepositoryError: If database operation fails
    """
    try:
        with get_session(db_path) as session:
            statement = select(Repository)
            repositories = session.exec(statement).all()
            return len(list(repositories))

    except Exception as e:
        raise RepositoryError(f"Failed to get repository count: {str(e)}") from e


def get_repository_info(alias: str, db_path: str | None = None) -> dict:
    """Get detailed repository information including search index count.

    Args:
        alias: Repository alias
        db_path: Optional custom database path

    Returns:
        Dictionary with repository information

    Raises:
        RepositoryNotFoundError: If repository is not found
        RepositoryError: If database operation fails
    """
    try:
        with get_session(db_path) as session:
            # Get repository
            repo_statement = select(Repository).where(Repository.alias == alias)
            repository = session.exec(repo_statement).first()

            if repository is None:
                raise RepositoryNotFoundError(
                    f"Repository with alias '{alias}' not found"
                )

            # Get search index count
            index_statement = select(SearchIndex).where(
                SearchIndex.repo_id == repository.id
            )
            search_indexes = session.exec(index_statement).all()
            index_count = len(list(search_indexes))

            return {
                "id": repository.id,
                "alias": repository.alias,
                "url": repository.url,
                "local_path": repository.local_path,
                "last_updated": repository.last_updated,
                "indexed": repository.indexed,
                "search_index_count": index_count,
            }

    except RepositoryNotFoundError:
        raise
    except Exception as e:
        raise RepositoryError(
            f"Failed to get repository info for '{alias}': {str(e)}"
        ) from e
