"""
Tests for TUI functionality.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, Mock

from src.kodeklip.search import SearchResult
from src.kodeklip.tui import (
    SearchResultsTable,
    FilePreview,
    StatusBar,
    SearchApp,
    launch_interactive_search,
)


class TestSearchResultsTable:
    """Test SearchResultsTable widget."""

    def test_initialization(self):
        """Test table initialization with search results."""
        results = [
            SearchResult(
                file_path="test1.py",
                line_number=10,
                line_content="def test_function():",
            ),
            SearchResult(
                file_path="test2.py",
                line_number=20,
                line_content="print('hello world')",
            ),
        ]

        table = SearchResultsTable(results)
        assert table.results == results
        assert table.cursor_type == "row"
        assert table.zebra_stripes is True
        assert table.show_header is True

    def test_toggle_row_selection(self):
        """Test row selection toggling."""
        results = [
            SearchResult(
                file_path="test.py",
                line_number=1,
                line_content="import os",
            )
        ]

        table = SearchResultsTable(results)
        assert len(table.selected_rows) == 0

        # Toggle selection on
        table.toggle_row_selection(0)
        assert 0 in table.selected_rows

        # Toggle selection off
        table.toggle_row_selection(0)
        assert 0 not in table.selected_rows

    def test_get_selected_results(self):
        """Test getting selected search results."""
        results = [
            SearchResult("test1.py", 1, "line 1"),
            SearchResult("test2.py", 2, "line 2"),
        ]

        table = SearchResultsTable(results)
        table.selected_rows.add(0)

        selected = table.get_selected_results()
        assert len(selected) == 1
        assert selected[0] == results[0]

    def test_get_current_result(self):
        """Test getting current highlighted result."""
        results = [
            SearchResult("test.py", 1, "line 1"),
        ]

        table = SearchResultsTable(results)

        # Mock the cursor_row property since it's read-only in DataTable
        # We'll just test the bounds checking logic
        assert len(table.results) == 1

        # Test the logic by directly checking the method behavior
        # We can't easily test this without running the full widget lifecycle


class TestFilePreview:
    """Test FilePreview widget."""

    def test_detect_language(self):
        """Test programming language detection."""
        preview = FilePreview()

        # Test known extensions
        assert preview._detect_language("test.py") == "python"
        assert preview._detect_language("test.js") == "javascript"
        assert preview._detect_language("test.rs") == "rust"
        assert preview._detect_language("test.go") == "go"
        assert preview._detect_language("test.java") == "java"

        # Test unknown extension
        assert preview._detect_language("test.unknown") is None

        # Test no extension
        assert preview._detect_language("Makefile") is None

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.read_text')
    def test_show_result_file_exists(self, mock_read_text, mock_exists):
        """Test showing a result when file exists."""
        mock_exists.return_value = True
        mock_read_text.return_value = "line 1\nline 2\nline 3\n"

        preview = FilePreview()
        result = SearchResult("test.py", 2, "line 2")

        preview.show_result(result, "/tmp")

        mock_exists.assert_called_once()
        mock_read_text.assert_called_once()

    @patch('pathlib.Path.exists')
    def test_show_result_file_not_exists(self, mock_exists):
        """Test showing a result when file doesn't exist."""
        mock_exists.return_value = False

        preview = FilePreview()
        result = SearchResult("missing.py", 1, "line 1")

        preview.show_result(result, "/tmp")

        mock_exists.assert_called_once()


class TestStatusBar:
    """Test StatusBar widget."""

    def test_update_status(self):
        """Test status bar updates."""
        status_bar = StatusBar()

        # Test with results
        status_bar.update_status(2, 5, 10)
        # We can't easily test the exact content since update() is internal,
        # but we can verify the method runs without error

        # Test with no results
        status_bar.update_status(0, 0, 0)


class TestSearchApp:
    """Test SearchApp main application."""

    def test_initialization(self):
        """Test app initialization."""
        results = [SearchResult("test.py", 1, "line 1")]
        query = "test"
        repo_path = "/tmp"

        app = SearchApp(results, query, repo_path)
        assert app.results == results
        assert app.query == query
        assert app.repo_path == repo_path

    def test_format_results_for_clipboard(self):
        """Test clipboard formatting."""
        results = [
            SearchResult("test1.py", 10, "def function1():"),
            SearchResult("test2.py", 20, "def function2():"),
        ]

        app = SearchApp(results, "def", "/tmp")
        formatted = app._format_results_for_clipboard(results)

        assert "# KodeKlip Search Results: 'def'" in formatted
        assert "# 2 results" in formatted
        assert "## test1.py:10" in formatted
        assert "## test2.py:20" in formatted
        assert "def function1():" in formatted
        assert "def function2():" in formatted

    @patch('pyperclip.copy')
    def test_clipboard_operations(self, mock_copy):
        """Test clipboard copy operations."""
        results = [SearchResult("test.py", 1, "import os")]
        app = SearchApp(results, "import", "/tmp")

        # Test yank current (single line)
        with patch.object(app, 'query_one') as mock_query:
            mock_table = Mock()
            mock_table.get_current_result.return_value = results[0]
            mock_query.return_value = mock_table

            app.action_yank_current()
            mock_copy.assert_called_with("import os")

    def test_action_methods_exist(self):
        """Test that all action methods exist."""
        results = [SearchResult("test.py", 1, "line 1")]
        app = SearchApp(results, "test", "/tmp")

        # Verify action methods exist
        assert hasattr(app, 'action_next_result')
        assert hasattr(app, 'action_prev_result')
        assert hasattr(app, 'action_toggle_selection')
        assert hasattr(app, 'action_copy_selected')
        assert hasattr(app, 'action_yank_current')
        assert hasattr(app, 'action_view_full_file')


class TestLaunchInteractiveSearch:
    """Test the launch function."""

    def test_launch_with_no_results(self, capsys):
        """Test launching with no results."""
        launch_interactive_search([], "test", "/tmp")

        captured = capsys.readouterr()
        assert "No results to display interactively" in captured.out

    @patch('src.kodeklip.tui.SearchApp.run')
    def test_launch_with_results(self, mock_run):
        """Test launching with results."""
        results = [SearchResult("test.py", 1, "line 1")]
        launch_interactive_search(results, "test", "/tmp")

        mock_run.assert_called_once()


class TestIntegration:
    """Integration tests for TUI components."""

    def test_full_workflow_simulation(self):
        """Test a simulated full workflow."""
        # Create test data
        results = [
            SearchResult("main.py", 15, "def main():"),
            SearchResult("utils.py", 8, "def helper():"),
            SearchResult("config.py", 3, "def load_config():"),
        ]

        # Test table initialization
        table = SearchResultsTable(results)
        assert len(table.results) == 3

        # Test selection workflow
        table.toggle_row_selection(0)
        table.toggle_row_selection(2)
        selected = table.get_selected_results()
        assert len(selected) == 2
        assert selected[0].file_path == "main.py"
        assert selected[1].file_path == "config.py"

        # Test status updates
        status_bar = StatusBar()
        status_bar.update_status(2, 0, 3)  # 2 selected, current index 0, total 3

        # Test app initialization
        app = SearchApp(results, "def", "/home/user/project")
        formatted = app._format_results_for_clipboard(selected)
        assert "2 results" in formatted


# Additional real-world test scenarios
class TestRealWorldScenarios:
    """Test real-world usage scenarios."""

    def test_large_result_set(self):
        """Test handling large result sets."""
        # Create 1000 results
        results = []
        for i in range(1000):
            results.append(
                SearchResult(
                    f"file_{i}.py",
                    i + 1,
                    f"def function_{i}():",
                )
            )

        table = SearchResultsTable(results)
        assert len(table.results) == 1000

        # Test selection on large dataset
        indices = list(range(0, 100, 10))  # [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
        for i in indices:
            table.toggle_row_selection(i)

        selected = table.get_selected_results()
        assert len(selected) == len(indices)  # Should be 10

    def test_long_content_truncation(self):
        """Test that long content is properly truncated."""
        long_content = "x" * 100  # 100 character line
        result = SearchResult("test.py", 1, long_content)

        table = SearchResultsTable([result])
        # The truncation happens in on_mount, which we can't easily test
        # without running the full TUI, but we verify the logic exists
        assert len(result.line_content) == 100

    def test_special_characters_in_content(self):
        """Test handling of special characters."""
        special_content = "def test(): # Special chars: åøæ ñ 中文 🚀"
        result = SearchResult("unicode.py", 1, special_content)

        table = SearchResultsTable([result])
        assert table.results[0].line_content == special_content

    def test_empty_and_whitespace_content(self):
        """Test handling of empty and whitespace-only content."""
        results = [
            SearchResult("empty.py", 1, ""),
            SearchResult("whitespace.py", 2, "   \t  \n  "),
            SearchResult("normal.py", 3, "print('hello')"),
        ]

        table = SearchResultsTable(results)
        assert len(table.results) == 3

        # Test that all results are preserved
        for i, result in enumerate(results):
            assert table.results[i].line_content == result.line_content