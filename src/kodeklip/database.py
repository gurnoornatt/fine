"""
Database initialization and session management for KodeKlip.

This module handles SQLite database setup, table creation, and provides
session management utilities for database operations.
"""

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy.engine.base import Engine
from sqlmodel import Session, SQLModel, create_engine, text


class DatabaseConfig:
    """Configuration for database setup."""

    def __init__(self, db_path: str | None = None):
        """Initialize database configuration.

        Args:
            db_path: Optional custom database path. Defaults to ~/.kodeklip/db.sqlite
        """
        if db_path is None:
            # Default to ~/.kodeklip/db.sqlite
            home = Path.home()
            self.kodeklip_dir = home / ".kodeklip"
            self.db_path = self.kodeklip_dir / "db.sqlite"
        else:
            self.db_path = Path(db_path)
            self.kodeklip_dir = self.db_path.parent

        self.database_url = f"sqlite:///{self.db_path}"


# Global engine instance
_engine: Engine | None = None
_config: DatabaseConfig | None = None


def get_engine(db_path: str | None = None) -> Engine:
    """Get or create SQLite engine instance.

    Args:
        db_path: Optional custom database path

    Returns:
        SQLAlchemy engine instance
    """
    global _engine, _config

    if _engine is None or (
        db_path is not None and _config and str(_config.db_path) != db_path
    ):
        _config = DatabaseConfig(db_path)

        # Ensure kodeklip directory exists
        _config.kodeklip_dir.mkdir(parents=True, exist_ok=True)

        # Create engine with WAL mode for better concurrency
        _engine = create_engine(
            _config.database_url,
            echo=False,  # Set to True for debugging SQL statements
            connect_args={
                "check_same_thread": False
            },  # Required for SQLite with threading
        )

        # Enable WAL mode for better performance and concurrency
        with _engine.connect() as connection:
            connection.execute(text("PRAGMA journal_mode=WAL"))
            connection.execute(
                text("PRAGMA foreign_keys=ON")
            )  # Enable foreign key constraints
            connection.commit()

    return _engine


def create_db_and_tables(db_path: str | None = None) -> None:
    """Create database and all tables.

    Args:
        db_path: Optional custom database path
    """
    engine = get_engine(db_path)

    # Import models to ensure they're registered with SQLModel

    # Create all tables
    SQLModel.metadata.create_all(engine)


@contextmanager
def get_session(db_path: str | None = None) -> Generator[Session, None, None]:
    """Get database session context manager.

    Args:
        db_path: Optional custom database path

    Yields:
        SQLModel Session instance

    Example:
        with get_session() as session:
            repository = Repository(alias="test", url="https://github.com/test/repo")
            session.add(repository)
            session.commit()
    """
    engine = get_engine(db_path)

    with Session(engine) as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


def get_database_info(db_path: str | None = None) -> dict[str, str | bool | float]:
    """Get database information and status.

    Args:
        db_path: Optional custom database path

    Returns:
        Dictionary with database information
    """
    config = DatabaseConfig(db_path)

    info: dict[str, str | bool | float] = {
        "database_path": str(config.db_path),
        "database_exists": config.db_path.exists(),
        "kodeklip_dir": str(config.kodeklip_dir),
        "dir_exists": config.kodeklip_dir.exists(),
    }

    if config.db_path.exists():
        # Get file size in MB
        size_bytes = config.db_path.stat().st_size
        info["size_mb"] = round(size_bytes / (1024 * 1024), 2)

    return info


def reset_database(db_path: str | None = None) -> None:
    """Reset database by dropping and recreating all tables.

    WARNING: This will delete all data!

    Args:
        db_path: Optional custom database path
    """
    global _engine, _config

    config = DatabaseConfig(db_path)

    # Close existing engine if it exists
    if _engine is not None:
        _engine.dispose()
        _engine = None
        _config = None

    # Remove database file if it exists
    if config.db_path.exists():
        config.db_path.unlink()

    # Recreate database and tables
    create_db_and_tables(db_path)


def close_engine() -> None:
    """Close the global engine connection.

    This is useful for testing when we need to ensure
    database files can be replaced or moved.
    """
    global _engine, _config

    if _engine is not None:
        _engine.dispose()
        _engine = None
        _config = None
