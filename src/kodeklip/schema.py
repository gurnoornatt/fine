"""
Database schema validation and migration utilities.

This module provides utilities for validating database schema integrity,
checking for data corruption, and preparing for future schema migrations.
"""

import shutil
from datetime import datetime
from pathlib import Path

from sqlmodel import text

from .database import DatabaseConfig, close_engine, get_session

# Current schema version - increment when making schema changes
SCHEMA_VERSION = 1


class SchemaError(Exception):
    """Base exception for schema operations."""

    pass


class SchemaValidationError(SchemaError):
    """Raised when schema validation fails."""

    pass


class SchemaMigrationError(SchemaError):
    """Raised when schema migration fails."""

    pass


def get_schema_version(db_path: str | None = None) -> int:
    """Get current database schema version.

    Args:
        db_path: Optional custom database path

    Returns:
        Schema version number (0 if not set)

    Raises:
        SchemaError: If unable to determine schema version
    """
    try:
        with get_session(db_path) as session:
            # Check if schema_version table exists
            result = session.exec(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name='schema_version'"
                )
            ).first()

            if not result:
                # No schema_version table, assume version 0 (pre-versioning)
                return 0

            # Get current version
            version_result = session.exec(
                text(
                    "SELECT version FROM schema_version ORDER BY id DESC LIMIT 1"
                )
            ).first()
            return int(version_result[0]) if version_result else 0

    except Exception as e:
        raise SchemaError(f"Failed to get schema version: {str(e)}") from e


def set_schema_version(version: int, db_path: str | None = None) -> None:
    """Set database schema version.

    Args:
        version: Schema version to set
        db_path: Optional custom database path

    Raises:
        SchemaError: If unable to set schema version
    """
    try:
        with get_session(db_path) as session:
            # Create schema_version table if it doesn't exist
            session.exec(
                text(
                    """
                CREATE TABLE IF NOT EXISTS schema_version (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
                )
            )

            # Insert new version
            session.exec(
                text("INSERT INTO schema_version (version) VALUES (:version)").params(
                    version=version
                )
            )
            session.commit()

    except Exception as e:
        raise SchemaError(f"Failed to set schema version: {str(e)}") from e


def validate_schema(db_path: str | None = None) -> dict[str, bool | str | int]:
    """Validate database schema integrity.

    Args:
        db_path: Optional custom database path

    Returns:
        Dictionary with validation results

    Raises:
        SchemaValidationError: If critical schema issues are found
    """
    try:
        config = DatabaseConfig(db_path)
        validation_results = {
            "database_exists": config.db_path.exists(),
            "schema_version": 0,
            "tables_exist": False,
            "foreign_keys_enabled": False,
            "indexes_exist": False,
            "data_integrity": False,
        }

        if not config.db_path.exists():
            return validation_results

        with get_session(db_path) as session:
            # Check schema version
            validation_results["schema_version"] = get_schema_version(db_path)

            # Check if required tables exist
            required_tables = ["repository", "searchindex"]
            existing_tables = []

            for table in required_tables:
                result = session.exec(
                    text(
                        "SELECT name FROM sqlite_master WHERE type='table' "
                        "AND name=:table"
                    ).params(table=table)
                ).first()
                if result:
                    existing_tables.append(table)

            validation_results["tables_exist"] = len(existing_tables) == len(
                required_tables
            )
            validation_results["existing_tables"] = existing_tables

            # Check foreign key support
            fk_result = session.exec(text("PRAGMA foreign_keys")).first()
            validation_results["foreign_keys_enabled"] = (
                bool(fk_result[0]) if fk_result else False
            )

            # Check indexes
            index_result = session.exec(
                text(
                    "SELECT name FROM sqlite_master WHERE type='index' "
                    "AND name NOT LIKE 'sqlite_%'"
                )
            ).all()
            validation_results["indexes_exist"] = len(list(index_result)) > 0

            # Basic data integrity check
            if validation_results["tables_exist"]:
                # Check for orphaned search indexes
                orphan_result = session.exec(
                    text(
                        """
                    SELECT COUNT(*) FROM searchindex
                    WHERE repo_id NOT IN (SELECT id FROM repository)
                """
                    )
                ).first()
                validation_results["orphaned_indexes"] = (
                    int(orphan_result[0]) if orphan_result else 0
                )
                validation_results["data_integrity"] = (
                    validation_results["orphaned_indexes"] == 0
                )

        return validation_results

    except Exception as e:
        raise SchemaValidationError(f"Schema validation failed: {str(e)}") from e


def create_backup(db_path: str | None = None, backup_dir: str | None = None) -> str:
    """Create a backup of the database.

    Args:
        db_path: Optional custom database path
        backup_dir: Optional backup directory (defaults to ~/.kodeklip/backups)

    Returns:
        Path to created backup file

    Raises:
        SchemaError: If backup creation fails
    """
    try:
        config = DatabaseConfig(db_path)

        if not config.db_path.exists():
            raise SchemaError("Database file does not exist")

        # Setup backup directory
        if backup_dir is None:
            backup_dir_path = config.kodeklip_dir / "backups"
        else:
            backup_dir_path = Path(backup_dir)

        backup_dir_path.mkdir(parents=True, exist_ok=True)

        # Create backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"db_backup_{timestamp}.sqlite"
        backup_path = backup_dir_path / backup_filename

        # Close any database connections to ensure file is not locked
        close_engine()

        # Copy database file
        shutil.copy2(config.db_path, backup_path)

        # Verify backup
        if not backup_path.exists():
            raise SchemaError("Backup file was not created")

        return str(backup_path)

    except Exception as e:
        raise SchemaError(f"Failed to create backup: {str(e)}") from e


def restore_backup(backup_path: str, db_path: str | None = None) -> None:
    """Restore database from backup.

    WARNING: This will overwrite the current database!

    Args:
        backup_path: Path to backup file to restore
        db_path: Optional custom database path

    Raises:
        SchemaError: If restore fails
    """
    try:
        config = DatabaseConfig(db_path)
        backup_file = Path(backup_path)

        if not backup_file.exists():
            raise SchemaError(f"Backup file does not exist: {backup_path}")

        # Ensure target directory exists
        config.kodeklip_dir.mkdir(parents=True, exist_ok=True)

        # Close any existing database connections
        close_engine()

        # Copy backup to database location
        shutil.copy2(backup_file, config.db_path)

        # Verify restore
        if not config.db_path.exists():
            raise SchemaError("Database restore failed")

        # Validate restored database
        validation = validate_schema(db_path)
        if not validation["database_exists"]:
            raise SchemaError("Restored database is not valid")

    except Exception as e:
        raise SchemaError(f"Failed to restore backup: {str(e)}") from e


def check_migration_needed(db_path: str | None = None) -> tuple[bool, int, int]:
    """Check if database migration is needed.

    Args:
        db_path: Optional custom database path

    Returns:
        Tuple of (migration_needed, current_version, target_version)

    Raises:
        SchemaError: If unable to check migration status
    """
    try:
        current_version = get_schema_version(db_path)
        target_version = SCHEMA_VERSION

        migration_needed = current_version < target_version

        return migration_needed, current_version, target_version

    except Exception as e:
        raise SchemaError(f"Failed to check migration status: {str(e)}") from e


def get_database_statistics(db_path: str | None = None) -> dict[str, int | float]:
    """Get database statistics and health information.

    Args:
        db_path: Optional custom database path

    Returns:
        Dictionary with database statistics

    Raises:
        SchemaError: If unable to gather statistics
    """
    try:
        config = DatabaseConfig(db_path)
        stats = {
            "database_size_mb": 0.0,
            "repository_count": 0,
            "search_index_count": 0,
            "indexed_repository_count": 0,
        }

        if not config.db_path.exists():
            return stats

        # Database file size
        size_bytes = config.db_path.stat().st_size
        stats["database_size_mb"] = round(size_bytes / (1024 * 1024), 2)

        with get_session(db_path) as session:
            # Repository count
            repo_count = session.exec(text("SELECT COUNT(*) FROM repository")).first()
            stats["repository_count"] = int(repo_count[0]) if repo_count else 0

            # Search index count
            index_count = session.exec(text("SELECT COUNT(*) FROM searchindex")).first()
            stats["search_index_count"] = int(index_count[0]) if index_count else 0

            # Indexed repository count
            indexed_count = session.exec(
                text("SELECT COUNT(*) FROM repository WHERE indexed = 1")
            ).first()
            stats["indexed_repository_count"] = (
                int(indexed_count[0]) if indexed_count else 0
            )

        return stats

    except Exception as e:
        raise SchemaError(f"Failed to get database statistics: {str(e)}") from e


def repair_database(
    db_path: str | None = None, create_backup: bool = True
) -> dict[str, bool | int]:
    """Attempt to repair common database issues.

    Args:
        db_path: Optional custom database path
        create_backup: Whether to create backup before repair

    Returns:
        Dictionary with repair results

    Raises:
        SchemaError: If repair fails
    """
    try:
        repair_results = {
            "backup_created": False,
            "foreign_keys_fixed": False,
            "orphaned_indexes_removed": 0,
            "schema_version_set": False,
        }

        # Create backup if requested
        if create_backup:
            try:
                create_backup(db_path)
                repair_results["backup_created"] = True
            except Exception:
                # Continue with repair even if backup fails
                pass

        with get_session(db_path) as session:
            # Enable foreign keys
            session.exec(text("PRAGMA foreign_keys=ON"))
            repair_results["foreign_keys_fixed"] = True

            # Remove orphaned search indexes
            orphan_result = session.exec(
                text(
                    """
                DELETE FROM searchindex
                WHERE repo_id NOT IN (SELECT id FROM repository)
            """
                )
            )
            session.commit()
            repair_results["orphaned_indexes_removed"] = (
                orphan_result.rowcount if orphan_result else 0
            )

            # Set schema version if not set
            current_version = get_schema_version(db_path)
            if current_version == 0:
                set_schema_version(SCHEMA_VERSION, db_path)
                repair_results["schema_version_set"] = True

        return repair_results

    except Exception as e:
        raise SchemaError(f"Database repair failed: {str(e)}") from e
