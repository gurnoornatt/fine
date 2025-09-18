"""
Tests for git_manager module using real repositories.

Tests git operations with actual public GitHub repositories to ensure
the implementation works correctly with real data.
"""

import shutil
import tempfile
from pathlib import Path

import pytest
from sqlmodel import Session

from kodeklip.database import DatabaseConfig, get_session, create_db_and_tables
from kodeklip.git_manager import GitRepository
from kodeklip.models import Repository


class TestGitRepository:
    """Test GitRepository class with real git operations."""

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

    def test_validate_repository_url_valid_urls(self, git_manager):
        """Test URL validation with valid repository URLs."""
        valid_urls = [
            "https://github.com/octocat/Hello-World.git",
            "https://github.com/octocat/Hello-World",
            "git@github.com:octocat/Hello-World.git",
            "git@github.com:octocat/Hello-World",
            "https://gitlab.com/gitlab-org/gitlab.git",
            "https://gitlab.com/gitlab-org/gitlab",
            "git@gitlab.com:gitlab-org/gitlab.git",
            "https://bitbucket.org/atlassian/bitbucket.git",
            "git@bitbucket.org:atlassian/bitbucket.git",
        ]

        for url in valid_urls:
            assert git_manager.validate_repository_url(url), f"URL should be valid: {url}"

    def test_validate_repository_url_invalid_urls(self, git_manager):
        """Test URL validation with invalid repository URLs."""
        invalid_urls = [
            "",
            None,
            "not-a-url",
            "https://example.com",
            "https://github.com",
            "https://github.com/",
            "https://github.com/user",
            "ftp://github.com/user/repo.git",
            "https://github.com/user/repo/with/extra/path",
        ]

        for url in invalid_urls:
            assert not git_manager.validate_repository_url(url), f"URL should be invalid: {url}"

    def test_clone_real_public_repository(self, git_manager):
        """Test cloning a real public GitHub repository."""
        # Use a small, stable public repository for testing
        test_url = "https://github.com/octocat/Hello-World.git"
        test_alias = "hello-world-test"

        # Ensure clean state
        local_path = git_manager._get_local_path(test_alias)
        if local_path.exists():
            shutil.rmtree(local_path)

        # Test cloning
        success, message, repo_record = git_manager.clone_repository(test_url, test_alias)

        try:
            assert success, f"Clone should succeed: {message}"
            assert "Successfully cloned" in message
            assert repo_record is not None
            assert repo_record.alias == test_alias
            assert repo_record.url == test_url
            assert local_path.exists()
            assert (local_path / ".git").exists()

            # Verify repository exists in database
            assert git_manager.repository_exists(test_alias)

            # Verify we can get repository info
            repo_info = git_manager.get_repository_info(test_alias)
            assert repo_info is not None
            assert repo_info.alias == test_alias

        finally:
            # Cleanup
            if local_path.exists():
                shutil.rmtree(local_path, ignore_errors=True)

    def test_clone_invalid_repository(self, git_manager):
        """Test cloning with invalid repository URL."""
        invalid_url = "https://github.com/nonexistent/nonexistent-repo-12345.git"
        test_alias = "invalid-repo-test"

        success, message, repo_record = git_manager.clone_repository(invalid_url, test_alias)

        assert not success, "Clone should fail for nonexistent repository"
        assert "not found" in message.lower() or "clone failed" in message.lower()
        assert repo_record is None

        # Ensure no local directory was created
        local_path = git_manager._get_local_path(test_alias)
        assert not local_path.exists()

        # Ensure no database record was created
        assert not git_manager.repository_exists(test_alias)

    def test_clone_duplicate_alias(self, git_manager):
        """Test cloning with duplicate alias."""
        test_url = "https://github.com/octocat/Hello-World.git"
        test_alias = "duplicate-test"

        # First clone should succeed
        success1, message1, repo1 = git_manager.clone_repository(test_url, test_alias)

        try:
            assert success1, f"First clone should succeed: {message1}"

            # Second clone with same alias should fail
            success2, message2, repo2 = git_manager.clone_repository(test_url, test_alias)

            assert not success2, "Second clone with same alias should fail"
            assert "already exists" in message2
            assert repo2 is None

        finally:
            # Cleanup
            local_path = git_manager._get_local_path(test_alias)
            if local_path.exists():
                shutil.rmtree(local_path, ignore_errors=True)

    def test_clone_invalid_alias(self, git_manager):
        """Test cloning with invalid alias."""
        test_url = "https://github.com/octocat/Hello-World.git"

        # Test empty alias
        success, message, repo = git_manager.clone_repository(test_url, "")
        assert not success
        assert "alias cannot be empty" in message.lower()

        # Test None alias
        success, message, repo = git_manager.clone_repository(test_url, None)
        assert not success
        assert "alias cannot be empty" in message.lower()

        # Test whitespace-only alias
        success, message, repo = git_manager.clone_repository(test_url, "   ")
        assert not success
        assert "alias cannot be empty" in message.lower()

    def test_clone_invalid_url(self, git_manager):
        """Test cloning with invalid URL."""
        invalid_urls = [
            "not-a-url",
            "https://example.com",
            "",
            None,
        ]

        for invalid_url in invalid_urls:
            success, message, repo = git_manager.clone_repository(invalid_url, "test-alias")
            assert not success, f"Should fail for invalid URL: {invalid_url}"
            assert "invalid repository url" in message.lower()
            assert repo is None

    def test_list_repositories(self, git_manager):
        """Test listing repositories."""
        # Initially should be empty
        repos = git_manager.list_repositories()
        initial_count = len(repos)

        # Clone a test repository
        test_url = "https://github.com/octocat/Hello-World.git"
        test_alias = "list-test"

        success, message, repo = git_manager.clone_repository(test_url, test_alias)

        try:
            assert success, f"Clone should succeed: {message}"

            # List should now include our repository
            repos = git_manager.list_repositories()
            assert len(repos) == initial_count + 1

            # Find our repository in the list
            our_repo = next((r for r in repos if r.alias == test_alias), None)
            assert our_repo is not None
            assert our_repo.url == test_url

        finally:
            # Cleanup
            local_path = git_manager._get_local_path(test_alias)
            if local_path.exists():
                shutil.rmtree(local_path, ignore_errors=True)

    def test_repository_exists(self, git_manager):
        """Test repository existence checking."""
        test_alias = "exists-test"

        # Should not exist initially
        assert not git_manager.repository_exists(test_alias)

        # Clone repository
        test_url = "https://github.com/octocat/Hello-World.git"
        success, message, repo = git_manager.clone_repository(test_url, test_alias)

        try:
            assert success, f"Clone should succeed: {message}"

            # Should exist after cloning
            assert git_manager.repository_exists(test_alias)

            # Should still exist if we just check again
            assert git_manager.repository_exists(test_alias)

        finally:
            # Cleanup
            local_path = git_manager._get_local_path(test_alias)
            if local_path.exists():
                shutil.rmtree(local_path, ignore_errors=True)

    def test_get_repository_info(self, git_manager):
        """Test getting repository information."""
        test_alias = "info-test"

        # Should return None for nonexistent repository
        info = git_manager.get_repository_info(test_alias)
        assert info is None

        # Clone repository
        test_url = "https://github.com/octocat/Hello-World.git"
        success, message, repo = git_manager.clone_repository(test_url, test_alias)

        try:
            assert success, f"Clone should succeed: {message}"

            # Should return repository info
            info = git_manager.get_repository_info(test_alias)
            assert info is not None
            assert info.alias == test_alias
            assert info.url == test_url
            assert info.indexed is False

        finally:
            # Cleanup
            local_path = git_manager._get_local_path(test_alias)
            if local_path.exists():
                shutil.rmtree(local_path, ignore_errors=True)