"""
Comprehensive tests for database operations with real data.

Tests all database functionality including models, CRUD operations, schema validation,
and error handling using real SQLite databases (no mocks).
"""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from kodeklip.database import (
    create_db_and_tables,
    get_database_info,
    get_session,
    reset_database,
)
from kodeklip.models import Repository, SearchIndex
from kodeklip.repository_manager import (
    RepositoryAlreadyExistsError,
    RepositoryError,
    RepositoryNotFoundError,
    add_repository,
    get_repository,
    get_repository_count,
    get_repository_info,
    list_repositories,
    remove_repository,
    repository_exists,
    update_repository_status,
)
from kodeklip.schema import (
    SCHEMA_VERSION,
    SchemaError,
    check_migration_needed,
    create_backup,
    get_database_statistics,
    get_schema_version,
    repair_database,
    restore_backup,
    set_schema_version,
    validate_schema,
)
from sqlmodel import Session, select


class TestDatabaseSetup:
    """Test database initialization and configuration."""

    def test_create_db_and_tables_with_custom_path(self):
        """Test database creation with custom path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"

            # Create database
            create_db_and_tables(str(db_path))

            # Verify database file exists
            assert db_path.exists()

            # Verify tables were created
            info = get_database_info(str(db_path))
            assert info["database_exists"] is True

    def test_get_database_info(self):
        """Test database information retrieval."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "info_test.db"

            # Test with non-existent database
            info = get_database_info(str(db_path))
            assert info["database_exists"] is False

            # Create database and test again
            create_db_and_tables(str(db_path))
            info = get_database_info(str(db_path))
            assert info["database_exists"] is True
            assert "size_mb" in info
            assert info["size_mb"] >= 0

    def test_reset_database(self):
        """Test database reset functionality."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "reset_test.db"

            # Create database and add data
            create_db_and_tables(str(db_path))
            add_repository(
                "test-repo", "https://github.com/test/repo", "/tmp/test", str(db_path)
            )

            # Verify data exists
            assert repository_exists("test-repo", str(db_path))

            # Reset database
            reset_database(str(db_path))

            # Verify database still exists but data is gone
            assert db_path.exists()
            assert not repository_exists("test-repo", str(db_path))

    def test_session_context_manager(self):
        """Test database session context manager."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "session_test.db"
            create_db_and_tables(str(db_path))

            # Test successful session
            with get_session(str(db_path)) as session:
                assert isinstance(session, Session)

                # Add data within session
                repo = Repository(
                    alias="test", url="https://test.com", local_path="/tmp"
                )
                session.add(repo)
                session.commit()

            # Verify data persisted
            with get_session(str(db_path)) as session:
                statement = select(Repository).where(Repository.alias == "test")
                result = session.exec(statement).first()
                assert result is not None
                assert result.alias == "test"


class TestModels:
    """Test SQLModel models and relationships."""

    def test_repository_model_creation(self):
        """Test Repository model creation and validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "model_test.db"
            create_db_and_tables(str(db_path))

            with get_session(str(db_path)) as session:
                # Create repository
                repo = Repository(
                    alias="test-repo",
                    url="https://github.com/test/repo",
                    local_path="/tmp/test-repo",
                    indexed=True,
                )
                session.add(repo)
                session.commit()
                session.refresh(repo)

                # Verify all fields
                assert repo.id is not None
                assert repo.alias == "test-repo"
                assert repo.url == "https://github.com/test/repo"
                assert repo.local_path == "/tmp/test-repo"
                assert repo.indexed is True
                assert repo.last_updated is None

    def test_search_index_model_creation(self):
        """Test SearchIndex model creation and validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "search_index_test.db"
            create_db_and_tables(str(db_path))

            with get_session(str(db_path)) as session:
                # Create repository first
                repo = Repository(
                    alias="parent-repo",
                    url="https://github.com/test/repo",
                    local_path="/tmp/parent-repo",
                )
                session.add(repo)
                session.commit()
                session.refresh(repo)

                # Create search index
                search_index = SearchIndex(
                    repo_id=repo.id,
                    file_path="src/main.py",
                    content_hash="abc123",
                    embedding_data='{"vector": [1, 2, 3]}',
                )
                session.add(search_index)
                session.commit()
                session.refresh(search_index)

                # Verify fields
                assert search_index.id is not None
                assert search_index.repo_id == repo.id
                assert search_index.file_path == "src/main.py"
                assert search_index.content_hash == "abc123"
                assert search_index.embedding_data == '{"vector": [1, 2, 3]}'
                assert search_index.created_at is not None

    def test_model_relationships(self):
        """Test relationships between Repository and SearchIndex models."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "relationship_test.db"
            create_db_and_tables(str(db_path))

            with get_session(str(db_path)) as session:
                # Create repository
                repo = Repository(
                    alias="relationship-test",
                    url="https://github.com/test/repo",
                    local_path="/tmp/relationship-test",
                )
                session.add(repo)
                session.commit()
                session.refresh(repo)

                # Create multiple search indexes
                for i in range(3):
                    search_index = SearchIndex(
                        repo_id=repo.id,
                        file_path=f"src/file{i}.py",
                        content_hash=f"hash{i}",
                    )
                    session.add(search_index)

                session.commit()

                # Test relationship - verify manual loading works
                index_statement = select(SearchIndex).where(
                    SearchIndex.repo_id == repo.id
                )
                indexes = session.exec(index_statement).all()

                assert len(list(indexes)) == 3


class TestRepositoryManager:
    """Test repository CRUD operations."""

    def test_add_repository(self):
        """Test adding repositories with various configurations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "add_test.db"
            create_db_and_tables(str(db_path))

            # Add repository
            repo = add_repository(
                "test-add", "https://github.com/test/add", "/tmp/test-add", str(db_path)
            )

            # Verify repository was added
            assert repo.alias == "test-add"
            assert repo.url == "https://github.com/test/add"
            assert repo.local_path == "/tmp/test-add"
            assert repo.indexed is False
            assert repo.last_updated is None

    def test_add_duplicate_repository(self):
        """Test adding duplicate repository raises error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "duplicate_test.db"
            create_db_and_tables(str(db_path))

            # Add first repository
            add_repository(
                "duplicate", "https://github.com/test/repo", "/tmp/test", str(db_path)
            )

            # Attempt to add duplicate should raise error
            with pytest.raises(RepositoryAlreadyExistsError):
                add_repository(
                    "duplicate",
                    "https://github.com/other/repo",
                    "/tmp/other",
                    str(db_path),
                )

    def test_get_repository(self):
        """Test retrieving repositories by alias."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "get_test.db"
            create_db_and_tables(str(db_path))

            # Add repository
            original = add_repository(
                "get-test", "https://github.com/test/get", "/tmp/get", str(db_path)
            )

            # Retrieve repository
            retrieved = get_repository("get-test", str(db_path))

            # Verify retrieved data matches
            assert retrieved.id == original.id
            assert retrieved.alias == original.alias
            assert retrieved.url == original.url
            assert retrieved.local_path == original.local_path

    def test_get_nonexistent_repository(self):
        """Test retrieving non-existent repository raises error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "nonexistent_test.db"
            create_db_and_tables(str(db_path))

            with pytest.raises(RepositoryNotFoundError):
                get_repository("does-not-exist", str(db_path))

    def test_list_repositories(self):
        """Test listing all repositories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "list_test.db"
            create_db_and_tables(str(db_path))

            # Add multiple repositories
            repos = []
            for i in range(3):
                repo = add_repository(
                    f"repo-{i}",
                    f"https://github.com/test/repo{i}",
                    f"/tmp/repo{i}",
                    str(db_path),
                )
                repos.append(repo)

            # List repositories
            listed = list_repositories(str(db_path))

            # Verify count and order (should be ordered by alias)
            assert len(listed) == 3
            assert [r.alias for r in listed] == ["repo-0", "repo-1", "repo-2"]

    def test_update_repository_status(self):
        """Test updating repository status information."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "update_test.db"
            create_db_and_tables(str(db_path))

            # Add repository
            add_repository(
                "update-test",
                "https://github.com/test/update",
                "/tmp/update",
                str(db_path),
            )

            # Update status
            now = datetime.now()
            updated = update_repository_status(
                "update-test", last_updated=now, indexed=True, db_path=str(db_path)
            )

            # Verify updates
            assert updated.last_updated == now
            assert updated.indexed is True

    def test_remove_repository(self):
        """Test removing repositories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "remove_test.db"
            create_db_and_tables(str(db_path))

            # Add repository with search index
            repo = add_repository(
                "remove-test",
                "https://github.com/test/remove",
                "/tmp/remove",
                str(db_path),
            )

            with get_session(str(db_path)) as session:
                search_index = SearchIndex(
                    repo_id=repo.id, file_path="test.py", content_hash="testhash"
                )
                session.add(search_index)
                session.commit()

            # Remove repository
            result = remove_repository("remove-test", str(db_path))
            assert result is True

            # Verify removal
            assert not repository_exists("remove-test", str(db_path))

            # Verify search indexes were also removed
            with get_session(str(db_path)) as session:
                statement = select(SearchIndex).where(SearchIndex.repo_id == repo.id)
                remaining_indexes = session.exec(statement).all()
                assert len(list(remaining_indexes)) == 0

    def test_remove_nonexistent_repository(self):
        """Test removing non-existent repository returns False."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "remove_nonexistent_test.db"
            create_db_and_tables(str(db_path))

            result = remove_repository("does-not-exist", str(db_path))
            assert result is False

    def test_repository_exists(self):
        """Test checking repository existence."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "exists_test.db"
            create_db_and_tables(str(db_path))

            # Test non-existent repository
            assert not repository_exists("does-not-exist", str(db_path))

            # Add repository and test again
            add_repository(
                "exists-test",
                "https://github.com/test/exists",
                "/tmp/exists",
                str(db_path),
            )
            assert repository_exists("exists-test", str(db_path))

    def test_get_repository_count(self):
        """Test getting repository count."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "count_test.db"
            create_db_and_tables(str(db_path))

            # Test empty database
            assert get_repository_count(str(db_path)) == 0

            # Add repositories and test count
            for i in range(5):
                add_repository(
                    f"count-{i}",
                    f"https://github.com/test/{i}",
                    f"/tmp/{i}",
                    str(db_path),
                )

            assert get_repository_count(str(db_path)) == 5

    def test_get_repository_info(self):
        """Test getting detailed repository information."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "info_test.db"
            create_db_and_tables(str(db_path))

            # Add repository
            repo = add_repository(
                "info-test", "https://github.com/test/info", "/tmp/info", str(db_path)
            )

            # Add search indexes
            with get_session(str(db_path)) as session:
                for i in range(2):
                    search_index = SearchIndex(
                        repo_id=repo.id,
                        file_path=f"file{i}.py",
                        content_hash=f"hash{i}",
                    )
                    session.add(search_index)
                session.commit()

            # Get repository info
            info = get_repository_info("info-test", str(db_path))

            # Verify info
            assert info["alias"] == "info-test"
            assert info["url"] == "https://github.com/test/info"
            assert info["search_index_count"] == 2
            assert info["indexed"] is False


class TestSchemaOperations:
    """Test schema validation and migration utilities."""

    def test_schema_version_operations(self):
        """Test schema version getting and setting."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "version_test.db"
            create_db_and_tables(str(db_path))

            # Test initial version (should be 0)
            version = get_schema_version(str(db_path))
            assert version == 0

            # Set version
            set_schema_version(5, str(db_path))

            # Verify version was set
            version = get_schema_version(str(db_path))
            assert version == 5

    def test_validate_schema(self):
        """Test schema validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "validate_test.db"

            # Test validation on non-existent database
            validation = validate_schema(str(db_path))
            assert validation["database_exists"] is False

            # Create database and validate
            create_db_and_tables(str(db_path))
            validation = validate_schema(str(db_path))

            assert validation["database_exists"] is True
            assert validation["tables_exist"] is True
            assert validation["data_integrity"] is True

    def test_backup_and_restore(self):
        """Test database backup and restore functionality."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "backup_test.db"
            backup_dir = Path(temp_dir) / "backups"

            # Create database with data
            create_db_and_tables(str(db_path))
            add_repository(
                "backup-test",
                "https://github.com/test/backup",
                "/tmp/backup",
                str(db_path),
            )

            # Create backup
            backup_path = create_backup(str(db_path), str(backup_dir))
            assert Path(backup_path).exists()

            # Modify original database
            add_repository(
                "backup-test-2",
                "https://github.com/test/backup2",
                "/tmp/backup2",
                str(db_path),
            )
            assert get_repository_count(str(db_path)) == 2

            # Restore from backup
            restore_backup(backup_path, str(db_path))

            # Verify restoration
            assert get_repository_count(str(db_path)) == 1
            assert repository_exists("backup-test", str(db_path))
            assert not repository_exists("backup-test-2", str(db_path))

    def test_check_migration_needed(self):
        """Test migration status checking."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "migration_test.db"
            create_db_and_tables(str(db_path))

            # Check migration status
            needed, current, target = check_migration_needed(str(db_path))

            assert current == 0  # New database starts at 0
            assert target == SCHEMA_VERSION
            assert needed == (current < target)

    def test_database_statistics(self):
        """Test database statistics gathering."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "stats_test.db"
            create_db_and_tables(str(db_path))

            # Get initial stats
            stats = get_database_statistics(str(db_path))
            assert stats["repository_count"] == 0
            assert stats["search_index_count"] == 0
            assert (
                stats["database_size_mb"] >= 0
            )  # SQLite files can be 0 size when empty

            # Add data and check stats again
            repo = add_repository(
                "stats-test",
                "https://github.com/test/stats",
                "/tmp/stats",
                str(db_path),
            )

            with get_session(str(db_path)) as session:
                search_index = SearchIndex(
                    repo_id=repo.id, file_path="test.py", content_hash="testhash"
                )
                session.add(search_index)
                session.commit()

            stats = get_database_statistics(str(db_path))
            assert stats["repository_count"] == 1
            assert stats["search_index_count"] == 1

    def test_repair_database(self):
        """Test database repair functionality."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "repair_test.db"
            create_db_and_tables(str(db_path))

            # Repair database
            repair_results = repair_database(str(db_path), create_backup=False)

            # Verify repair results
            assert repair_results["foreign_keys_fixed"] is True
            assert (
                repair_results["orphaned_indexes_removed"] == 0
            )  # No orphaned indexes in clean DB
            assert (
                repair_results["schema_version_set"] is True
            )  # Version was 0, should be set


class TestErrorHandling:
    """Test error handling in database operations."""

    def test_database_operations_with_invalid_path(self):
        """Test database operations with invalid paths."""
        invalid_path = "/invalid/path/that/does/not/exist/test.db"

        # These should raise RepositoryError due to unable to create directory
        with pytest.raises(RepositoryError):
            add_repository(
                "test", "https://github.com/test/repo", "/tmp/test", invalid_path
            )

    def test_schema_operations_with_invalid_path(self):
        """Test schema operations with invalid database paths."""
        invalid_path = "/invalid/path/test.db"

        # Should raise SchemaError
        with pytest.raises(SchemaError):
            create_backup(invalid_path)

    def test_corrupted_database_handling(self):
        """Test handling of corrupted database operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "corrupted.db"

            # Create a file that's not a valid SQLite database
            with open(db_path, "w") as f:
                f.write("This is not a SQLite database")

            # Operations should raise appropriate errors
            with pytest.raises(RepositoryError):
                add_repository(
                    "test", "https://github.com/test/repo", "/tmp/test", str(db_path)
                )
