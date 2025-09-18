"""
Test the CLI entry point and basic commands.

These tests use real CLI invocations to ensure the interface works correctly.
"""

from kodeklip.main import app
from typer.testing import CliRunner

# Create a test runner
runner = CliRunner()


def test_cli_help():
    """Test that the CLI shows help information."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "KodeKlip" in result.output
    assert "Surgical Code Context Management Tool" in result.output
    assert "Fight context bloat" in result.output


def test_cli_version():
    """Test that the CLI shows version information."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "KodeKlip" in result.output
    assert "version" in result.output
    assert "0.1.0" in result.output


def test_add_command_help():
    """Test that the add command shows help."""
    result = runner.invoke(app, ["add", "--help"])
    assert result.exit_code == 0
    assert "Add a repository" in result.output
    assert "repo_url" in result.output


def test_list_command_help():
    """Test that the list command shows help."""
    result = runner.invoke(app, ["list", "--help"])
    assert result.exit_code == 0
    assert "List all repositories" in result.output


def test_find_command_help():
    """Test that the find command shows help."""
    result = runner.invoke(app, ["find", "--help"])
    assert result.exit_code == 0
    assert "Search for code patterns" in result.output
    assert "--interactive" in result.output
    assert "--semantic" in result.output


def test_index_command_help():
    """Test that the index command shows help."""
    result = runner.invoke(app, ["index", "--help"])
    assert result.exit_code == 0
    assert "Index a repository" in result.output
    assert "semantic search" in result.output


def test_add_command_placeholder():
    """Test that add command shows placeholder message."""
    result = runner.invoke(app, ["add", "https://github.com/test/repo"])
    assert result.exit_code == 0
    assert "Adding repository" in result.output
    assert "Not implemented yet" in result.output


def test_list_command_placeholder():
    """Test that list command shows placeholder data."""
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "Repository Knowledge Base" in result.output
    assert "Sample data shown" in result.output


def test_find_command_placeholder():
    """Test that find command shows placeholder message."""
    result = runner.invoke(app, ["find", "test-repo", "test-query"])
    assert result.exit_code == 0
    assert "Searching in: test-repo" in result.output
    assert "Query: 'test-query'" in result.output
    assert "Not implemented yet" in result.output


def test_find_command_with_options():
    """Test find command with various options."""
    result = runner.invoke(
        app,
        [
            "find",
            "test-repo",
            "test-query",
            "--interactive",
            "--type",
            "py",
            "--semantic",
            "--context",
            "3",
        ],
    )
    assert result.exit_code == 0
    assert "Searching in: test-repo" in result.output
    assert "Query: 'test-query'" in result.output
    assert "semantic search" in result.output
    assert "interactive TUI" in result.output
    assert "File type filter: py" in result.output
    assert "Context lines: 3" in result.output


def test_index_command_placeholder():
    """Test that index command shows placeholder message."""
    result = runner.invoke(app, ["index", "test-repo"])
    assert result.exit_code == 0
    assert "Indexing repository: test-repo" in result.output
    assert "tree-sitter + FAISS" in result.output
    assert "Not implemented yet" in result.output


def test_remove_command_help():
    """Test that the remove command shows help."""
    result = runner.invoke(app, ["remove", "--help"])
    assert result.exit_code == 0
    assert "Remove a repository" in result.output
    assert "--force" in result.output


def test_remove_command_with_force():
    """Test remove command with force flag."""
    result = runner.invoke(app, ["remove", "test-repo", "--force"])
    assert result.exit_code == 0
    assert "Removing repository: test-repo" in result.output
    assert "Not implemented yet" in result.output


def test_no_args_shows_help():
    """Test that running CLI without args shows help."""
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    # Should show help when no args provided due to no_args_is_help=True
    assert "Usage:" in result.output or "KodeKlip" in result.output


def test_invalid_command():
    """Test that invalid command shows appropriate error."""
    result = runner.invoke(app, ["invalid-command"])
    assert result.exit_code != 0
    # Typer should show an error for invalid commands
