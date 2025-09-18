"""
CLI integration tests using Typer CliRunner with real repositories.

Tests all CLI commands with actual git operations and real data.
"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from kodeklip.database import create_db_and_tables
from kodeklip.main import app


class TestCLI:
    """Test CLI commands with real git operations."""

    def setup_method(self):
        """Set up test environment with temporary database."""
        self.temp_dir = tempfile.mkdtemp()

        # Use CliRunner with isolated filesystem to test CLI naturally
        self.runner = CliRunner()

    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_help_command(self):
        """Test that CLI shows help correctly."""
        result = self.runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "KodeKlip" in result.output
        assert "Surgical Code Context Management Tool" in result.output

    def test_list_empty_repositories(self):
        """Test list command with no repositories."""
        result = self.runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "No repositories found" in result.output

    def test_add_repository_success(self):
        """Test adding a real public repository."""
        with self.runner.isolated_filesystem():
            # Use a small, stable public repository
            repo_url = "https://github.com/octocat/Hello-World.git"
            alias = "hello-world-test"

            result = self.runner.invoke(app, ["add", repo_url, alias])

            # Debug output
            print(f"\nExit code: {result.exit_code}")
            print(f"Output: {result.output}")
            if result.exception:
                print(f"Exception: {result.exception}")

            # Should succeed
            assert result.exit_code == 0
            assert "Adding repository" in result.output
            assert "Successfully cloned" in result.output

            # Cleanup
            cleanup_result = self.runner.invoke(app, ["remove", alias, "--force"])
            assert cleanup_result.exit_code == 0

    def test_add_repository_invalid_url(self):
        """Test adding repository with invalid URL."""
        result = self.runner.invoke(app, ["add", "not-a-url", "test"])

        assert result.exit_code == 1
        assert "Invalid repository URL" in result.output

    def test_add_repository_auto_alias(self):
        """Test adding repository with auto-generated alias."""
        repo_url = "https://github.com/octocat/Hello-World.git"

        result = self.runner.invoke(app, ["add", repo_url])

        # Should succeed and auto-generate alias
        assert result.exit_code == 0
        assert "Adding repository" in result.output
        assert "Hello-World" in result.output  # Auto-generated alias

        # Cleanup
        cleanup_result = self.runner.invoke(app, ["remove", "Hello-World", "--force"])
        assert cleanup_result.exit_code == 0

    def test_add_duplicate_repository(self):
        """Test adding duplicate repository."""
        repo_url = "https://github.com/octocat/Hello-World.git"
        alias = "duplicate-test"

        # First add should succeed
        result1 = self.runner.invoke(app, ["add", repo_url, alias])
        assert result1.exit_code == 0

        try:
            # Second add should fail
            result2 = self.runner.invoke(app, ["add", repo_url, alias])
            assert result2.exit_code == 1
            assert "already exists" in result2.output

        finally:
            # Cleanup
            cleanup_result = self.runner.invoke(app, ["remove", alias, "--force"])
            assert cleanup_result.exit_code == 0

    def test_full_workflow(self):
        """Test complete add -> list -> update -> remove workflow."""
        repo_url = "https://github.com/octocat/Hello-World.git"
        alias = "workflow-test"

        # Step 1: Add repository
        add_result = self.runner.invoke(app, ["add", repo_url, alias])
        assert add_result.exit_code == 0
        assert "Successfully cloned" in add_result.output

        # Step 2: List repositories
        list_result = self.runner.invoke(app, ["list"])
        assert list_result.exit_code == 0
        assert alias in list_result.output

        # Step 3: Update repository
        update_result = self.runner.invoke(app, ["update", alias])
        assert update_result.exit_code == 0

        # Step 4: Remove repository
        remove_result = self.runner.invoke(app, ["remove", alias, "--force"])
        assert remove_result.exit_code == 0

        # Step 5: Verify removal
        final_list = self.runner.invoke(app, ["list"])
        assert final_list.exit_code == 0
        assert alias not in final_list.output

    def test_invalid_alias_characters(self):
        """Test validation of alias characters."""
        repo_url = "https://github.com/octocat/Hello-World.git"
        invalid_aliases = ["test/alias", "test space", "test@alias", "test$"]

        for invalid_alias in invalid_aliases:
            result = self.runner.invoke(app, ["add", repo_url, invalid_alias])
            assert result.exit_code == 1
            assert "Invalid alias" in result.output