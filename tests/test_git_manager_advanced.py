"""
Advanced tests for git_manager module covering update, synchronization, and management operations.

Tests the more advanced functionality of GitRepository including updates,
cleanup operations, and repository management with real repositories.
"""

import shutil
import tempfile
from pathlib import Path

import pytest

from kodeklip.database import DatabaseConfig, get_session, create_db_and_tables
from kodeklip.git_manager import GitRepository
from kodeklip.models import Repository


class TestGitRepositoryAdvanced:
    """Test advanced GitRepository functionality with real git operations."""

    @pytest.fixture
    def temp_db_dir(self):
        """Create temporary directory for test database."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def git_manager(self, temp_db_dir):
        """Create GitRepository instance with temporary database."""
        db_path = Path(temp_db_dir) / "test.db"
        # Initialize database tables
        create_db_and_tables(str(db_path))
        return GitRepository(str(db_path))

    def test_update_repository(self, git_manager):
        """Test updating a real repository."""
        # Clone a repository first
        test_url = "https://github.com/octocat/Hello-World.git"
        test_alias = "update-test"

        success, message, repo = git_manager.clone_repository(test_url, test_alias)

        try:
            assert success, f"Clone should succeed: {message}"

            # Test updating (should be up to date since we just cloned)
            success, message, has_changes = git_manager.update_repository(test_alias)

            assert success, f"Update should succeed: {message}"
            assert "up to date" in message.lower() or "updated" in message.lower()
            # For a fresh clone, usually no changes unless the repo is very active
            assert isinstance(has_changes, bool)

            # Test updating non-existent repository
            success, message, has_changes = git_manager.update_repository("nonexistent")
            assert not success
            assert "does not exist" in message

        finally:
            # Cleanup
            local_path = git_manager._get_local_path(test_alias)
            if local_path.exists():
                shutil.rmtree(local_path, ignore_errors=True)

    def test_check_remote_updates(self, git_manager):
        """Test checking for remote updates."""
        # Clone a repository first
        test_url = "https://github.com/octocat/Hello-World.git"
        test_alias = "remote-check-test"

        success, message, repo = git_manager.clone_repository(test_url, test_alias)

        try:
            assert success, f"Clone should succeed: {message}"

            # Check for remote updates
            success, message, has_updates = git_manager.check_remote_updates(test_alias)

            assert success, f"Remote check should succeed: {message}"
            assert isinstance(has_updates, bool)
            assert "up to date" in message.lower() or "updates available" in message.lower()

        finally:
            # Cleanup
            local_path = git_manager._get_local_path(test_alias)
            if local_path.exists():
                shutil.rmtree(local_path, ignore_errors=True)

    def test_get_repository_status(self, git_manager):
        """Test getting detailed repository status."""
        # Clone a repository first
        test_url = "https://github.com/octocat/Hello-World.git"
        test_alias = "status-test"

        success, message, repo = git_manager.clone_repository(test_url, test_alias)

        try:
            assert success, f"Clone should succeed: {message}"

            # Get repository status
            success, message, status = git_manager.get_repository_status(test_alias)

            assert success, f"Status check should succeed: {message}"
            assert status["alias"] == test_alias
            assert status["exists"] is True
            assert status["is_git_repo"] is True
            assert "current_branch" in status
            assert "total_commits" in status
            assert isinstance(status["total_commits"], int)
            assert status["total_commits"] > 0
            assert "is_dirty" in status
            assert "has_remote" in status
            assert status["has_remote"] is True

        finally:
            # Cleanup
            local_path = git_manager._get_local_path(test_alias)
            if local_path.exists():
                shutil.rmtree(local_path, ignore_errors=True)

    def test_remove_repository(self, git_manager):
        """Test removing a repository."""
        # Clone a repository first
        test_url = "https://github.com/octocat/Hello-World.git"
        test_alias = "remove-test"

        success, message, repo = git_manager.clone_repository(test_url, test_alias)
        assert success, f"Clone should succeed: {message}"

        local_path = git_manager._get_local_path(test_alias)
        assert local_path.exists(), "Local repository should exist"

        # Test removal
        success, message = git_manager.remove_repository(test_alias)

        assert success, f"Removal should succeed: {message}"
        assert "successfully removed" in message.lower()
        assert not local_path.exists(), "Local repository should be removed"
        assert not git_manager.repository_exists(test_alias), "Repository should not exist in database"

    def test_remove_repository_keep_files(self, git_manager):
        """Test removing repository from database but keeping files."""
        # Clone a repository first
        test_url = "https://github.com/octocat/Hello-World.git"
        test_alias = "remove-keep-test"

        success, message, repo = git_manager.clone_repository(test_url, test_alias)
        assert success, f"Clone should succeed: {message}"

        local_path = git_manager._get_local_path(test_alias)
        assert local_path.exists(), "Local repository should exist"

        # Test removal with keep_files=True
        success, message = git_manager.remove_repository(test_alias, keep_files=True)

        try:
            assert success, f"Removal should succeed: {message}"
            assert "kept local files" in message.lower()
            assert local_path.exists(), "Local repository should still exist"
            assert not git_manager.repository_exists(test_alias), "Repository should not exist in database"

        finally:
            # Cleanup manually since we kept files
            if local_path.exists():
                shutil.rmtree(local_path, ignore_errors=True)

    def test_remove_nonexistent_repository(self, git_manager):
        """Test removing a repository that doesn't exist."""
        success, message = git_manager.remove_repository("nonexistent")

        assert not success
        assert "not found" in message.lower()

    def test_cleanup_orphaned_files(self, git_manager):
        """Test cleaning up orphaned repository directories."""
        # Create an orphaned directory (not in database)
        orphaned_dir = git_manager.repos_dir / "orphaned-repo"
        orphaned_dir.mkdir(parents=True, exist_ok=True)
        (orphaned_dir / "test.txt").write_text("test content")

        # Test cleanup
        success, message, cleanup_info = git_manager.cleanup_orphaned_files()

        assert success, f"Cleanup should succeed: {message}"
        assert "orphaned-repo" in cleanup_info["orphaned_dirs"]
        assert "orphaned-repo" in cleanup_info["removed_dirs"]
        assert not orphaned_dir.exists(), "Orphaned directory should be removed"
        assert cleanup_info["space_freed_mb"] > 0

    def test_sync_database_with_filesystem(self, git_manager):
        """Test synchronizing database with filesystem."""
        # Test with clean state first
        success, message, sync_info = git_manager.sync_database_with_filesystem()

        assert success, f"Sync should succeed: {message}"
        assert "synchronized" in message.lower()

        # Clone a repository and then manually remove its local files
        test_url = "https://github.com/octocat/Hello-World.git"
        test_alias = "sync-test"

        success, message, repo = git_manager.clone_repository(test_url, test_alias)
        assert success, f"Clone should succeed: {message}"

        # Manually remove local files to create inconsistency
        local_path = git_manager._get_local_path(test_alias)
        shutil.rmtree(local_path, ignore_errors=True)

        # Sync should detect and fix the inconsistency
        success, message, sync_info = git_manager.sync_database_with_filesystem()

        assert success, f"Sync should succeed: {message}"
        assert test_alias in sync_info["missing_repos"]
        assert test_alias in sync_info["removed_records"]
        assert not git_manager.repository_exists(test_alias)

    def test_get_disk_usage(self, git_manager):
        """Test calculating disk usage."""
        # Test with no repositories
        success, message, usage_info = git_manager.get_disk_usage()

        assert success, f"Disk usage check should succeed: {message}"
        assert usage_info["total_repos"] == 0
        assert usage_info["total_size_mb"] == 0.0

        # Clone a repository and check usage
        test_url = "https://github.com/octocat/Hello-World.git"
        test_alias = "usage-test"

        success, message, repo = git_manager.clone_repository(test_url, test_alias)

        try:
            assert success, f"Clone should succeed: {message}"

            success, message, usage_info = git_manager.get_disk_usage()

            assert success, f"Disk usage check should succeed: {message}"
            assert usage_info["total_repos"] == 1
            assert usage_info["total_size_mb"] > 0
            assert test_alias in usage_info["repo_sizes"]
            assert usage_info["repo_sizes"][test_alias] > 0
            assert usage_info["avg_size_mb"] > 0
            assert len(usage_info["largest_repos"]) == 1
            assert usage_info["largest_repos"][0][0] == test_alias

        finally:
            # Cleanup
            local_path = git_manager._get_local_path(test_alias)
            if local_path.exists():
                shutil.rmtree(local_path, ignore_errors=True)