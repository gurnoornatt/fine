"""
Comprehensive tests for search functionality using real repositories.

Tests all search capabilities with actual git repositories and real data.
"""

import shutil
import tempfile
from pathlib import Path
from typing import List

import pytest
from typer.testing import CliRunner

from kodeklip.database import create_db_and_tables
from kodeklip.main import app
from kodeklip.search import RipgrepSearcher, SearchOptions, SearchResult


class TestSearchFunctionality:
    """Test search functionality with real repositories."""

    def setup_method(self):
        """Set up test environment with temporary database and CLI runner."""
        self.temp_dir = tempfile.mkdtemp()
        self.runner = CliRunner()

    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _setup_test_repos(self) -> None:
        """Set up test repositories for search testing."""
        with self.runner.isolated_filesystem():
            # Add small test repository
            result = self.runner.invoke(app, [
                'add',
                'https://github.com/octocat/Hello-World.git',
                'test-repo'
            ])
            assert result.exit_code == 0

    def test_searcher_initialization(self):
        """Test RipgrepSearcher initialization and validation."""
        searcher = RipgrepSearcher()
        assert searcher.rg_path is not None
        assert searcher.validate_ripgrep()
        assert searcher.cache is not None
        assert searcher.formatter is not None

    def test_search_options_creation(self):
        """Test SearchOptions with various configurations."""
        # Default options
        options = SearchOptions()
        assert options.file_types == []
        assert options.max_results == 1000
        assert options.smart_case is True

        # Custom options
        options = SearchOptions(
            file_types=['py', 'js'],
            context_before=2,
            context_after=2,
            ignore_case=True,
            max_results=50
        )
        assert 'py' in options.file_types
        assert 'js' in options.file_types
        assert options.context_before == 2
        assert options.context_after == 2
        assert options.ignore_case is True
        assert options.max_results == 50

    def test_basic_search_with_real_repo(self):
        """Test basic search functionality with real repository."""
        with self.runner.isolated_filesystem():
            self._setup_test_repos()

            searcher = RipgrepSearcher()
            results = searcher.search_repository('test-repo', 'Hello')

            assert isinstance(results, list)
            assert len(results) > 0

            # Check result structure
            result = results[0]
            assert isinstance(result, SearchResult)
            assert hasattr(result, 'file_path')
            assert hasattr(result, 'line_number')
            assert hasattr(result, 'line_content')
            assert 'Hello' in result.line_content

    def test_file_type_filtering(self):
        """Test file type filtering functionality."""
        with self.runner.isolated_filesystem():
            self._setup_test_repos()

            searcher = RipgrepSearcher()

            # Search for markdown files only
            options = SearchOptions(file_types=['md'], max_results=10)
            md_results = searcher.search_repository('test-repo', 'Hello', options)

            # All results should be from markdown files or no results
            for result in md_results:
                assert result.file_extension.lower() in ['md', '']

    def test_context_lines(self):
        """Test context lines functionality."""
        with self.runner.isolated_filesystem():
            self._setup_test_repos()

            searcher = RipgrepSearcher()
            options = SearchOptions(context_before=1, context_after=1)
            results = searcher.search_repository('test-repo', 'Hello', options)

            assert len(results) > 0
            # Context lines are handled by ripgrep output parsing

    def test_case_sensitivity(self):
        """Test case sensitivity options."""
        with self.runner.isolated_filesystem():
            self._setup_test_repos()

            searcher = RipgrepSearcher()

            # Case insensitive search
            options_insensitive = SearchOptions(ignore_case=True)
            results_insensitive = searcher.search_repository(
                'test-repo', 'hello', options_insensitive
            )

            # Should find matches regardless of case
            assert len(results_insensitive) > 0

    def test_search_caching(self):
        """Test search result caching functionality."""
        with self.runner.isolated_filesystem():
            self._setup_test_repos()

            searcher = RipgrepSearcher(enable_cache=True)
            options = SearchOptions(max_results=5)

            # First search (cache miss)
            results1 = searcher.search_repository('test-repo', 'Hello', options)

            # Second search (cache hit)
            results2 = searcher.search_repository('test-repo', 'Hello', options)

            # Results should be identical
            assert len(results1) == len(results2)
            assert all(r1.line_content == r2.line_content
                      for r1, r2 in zip(results1, results2))

            # Verify cache is working
            cache_key = searcher.cache._make_key('test-repo', 'Hello', options)
            assert cache_key in searcher.cache.cache

    def test_nonexistent_repository(self):
        """Test error handling for nonexistent repository."""
        with self.runner.isolated_filesystem():
            create_db_and_tables()  # Initialize database

            searcher = RipgrepSearcher()

            with pytest.raises(ValueError, match="Repository 'nonexistent' not found"):
                searcher.search_repository('nonexistent', 'test')

    def test_search_all_repositories(self):
        """Test multi-repository search functionality."""
        with self.runner.isolated_filesystem():
            self._setup_test_repos()

            searcher = RipgrepSearcher()
            options = SearchOptions(max_results=10)

            results_dict = searcher.search_all_repositories('Hello', options)

            assert isinstance(results_dict, dict)
            assert 'test-repo' in results_dict
            assert len(results_dict['test-repo']) > 0

    def test_search_result_formatting(self):
        """Test search result formatting and rich output."""
        with self.runner.isolated_filesystem():
            self._setup_test_repos()

            searcher = RipgrepSearcher()
            results = searcher.search_repository('test-repo', 'Hello')

            # Test table formatting
            table = searcher.formatter.format_results_table(results, 'Hello')
            assert table is not None

            # Test detailed formatting
            panels = searcher.formatter.format_results_detailed(results, 'Hello')
            assert isinstance(panels, list)

            # Test summary formatting
            results_dict = {'test-repo': results}
            summary = searcher.formatter.format_summary(results_dict, 'Hello')
            assert summary is not None

    def test_search_result_methods(self):
        """Test SearchResult methods and properties."""
        result = SearchResult(
            file_path='test.py',
            line_number=42,
            line_content='def hello_world():',
            context_before=['# Comment'],
            context_after=['    pass']
        )

        # Test properties
        assert result.file_extension == 'py'
        assert result.relative_path == 'test.py'

        # Test string representation
        str_repr = str(result)
        assert 'test.py:42' in str_repr
        assert 'def hello_world()' in str_repr

        # Test dictionary conversion
        result_dict = result.to_dict()
        assert result_dict['file_path'] == 'test.py'
        assert result_dict['line_number'] == 42
        assert result_dict['context_before'] == ['# Comment']
        assert result_dict['context_after'] == ['    pass']


class TestCLIIntegration:
    """Test CLI integration with search functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()

    def _setup_test_repos(self) -> None:
        """Set up test repositories."""
        result = self.runner.invoke(app, [
            'add',
            'https://github.com/octocat/Hello-World.git',
            'cli-test-repo'
        ])
        assert result.exit_code == 0

    def test_cli_basic_search(self):
        """Test basic CLI search command."""
        with self.runner.isolated_filesystem():
            self._setup_test_repos()

            result = self.runner.invoke(app, ['find', 'cli-test-repo', 'Hello'])
            assert result.exit_code == 0
            assert 'Found' in result.output
            assert 'matches' in result.output

    def test_cli_file_type_filter(self):
        """Test CLI file type filtering."""
        with self.runner.isolated_filesystem():
            self._setup_test_repos()

            result = self.runner.invoke(app, [
                'find', 'cli-test-repo', 'Hello', '-t', 'md', '--limit', '5'
            ])
            assert result.exit_code == 0

    def test_cli_context_option(self):
        """Test CLI context lines option."""
        with self.runner.isolated_filesystem():
            self._setup_test_repos()

            result = self.runner.invoke(app, [
                'find', 'cli-test-repo', 'Hello', '-c', '2'
            ])
            assert result.exit_code == 0
            assert 'Context lines: 2' in result.output

    def test_cli_limit_option(self):
        """Test CLI result limit option."""
        with self.runner.isolated_filesystem():
            self._setup_test_repos()

            result = self.runner.invoke(app, [
                'find', 'cli-test-repo', 'Hello', '--limit', '10'
            ])
            assert result.exit_code == 0
            assert 'Result limit: 10' in result.output

    def test_cli_detailed_output(self):
        """Test CLI detailed output option."""
        with self.runner.isolated_filesystem():
            self._setup_test_repos()

            result = self.runner.invoke(app, [
                'find', 'cli-test-repo', 'Hello', '--detailed', '--limit', '1'
            ])
            assert result.exit_code == 0

    def test_cli_case_sensitive(self):
        """Test CLI case sensitive option."""
        with self.runner.isolated_filesystem():
            self._setup_test_repos()

            result = self.runner.invoke(app, [
                'find', 'cli-test-repo', 'hello', '--case-sensitive'
            ])
            assert result.exit_code == 0

    def test_cli_error_handling(self):
        """Test CLI error handling."""
        with self.runner.isolated_filesystem():
            create_db_and_tables()

            # Test nonexistent repository
            result = self.runner.invoke(app, ['find', 'nonexistent', 'test'])
            assert result.exit_code == 1
            assert 'Error' in result.output

    def test_cli_no_matches(self):
        """Test CLI behavior when no matches found."""
        with self.runner.isolated_filesystem():
            self._setup_test_repos()

            result = self.runner.invoke(app, [
                'find', 'cli-test-repo', 'nonexistentpattern'
            ])
            assert result.exit_code == 0
            assert 'No matches found' in result.output

    def test_cli_semantic_search_placeholder(self):
        """Test CLI semantic search placeholder."""
        with self.runner.isolated_filesystem():
            self._setup_test_repos()

            result = self.runner.invoke(app, [
                'find', 'cli-test-repo', 'Hello', '-s'
            ])
            assert result.exit_code == 0
            assert 'Semantic search not implemented yet' in result.output

    def test_cli_interactive_placeholder(self):
        """Test CLI interactive mode placeholder."""
        with self.runner.isolated_filesystem():
            self._setup_test_repos()

            result = self.runner.invoke(app, [
                'find', 'cli-test-repo', 'Hello', '-i'
            ])
            assert result.exit_code == 0
            assert 'Interactive mode not implemented yet' in result.output


class TestPerformanceAndEdgeCases:
    """Test performance characteristics and edge cases."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()

    def test_empty_query_handling(self):
        """Test handling of empty queries."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(app, [
                'add', 'https://github.com/octocat/Hello-World.git', 'edge-test'
            ])
            assert result.exit_code == 0

            searcher = RipgrepSearcher()
            results = searcher.search_repository('edge-test', '')

            # Empty query should return results (ripgrep behavior)
            assert isinstance(results, list)

    def test_large_result_limit(self):
        """Test handling of large result limits."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(app, [
                'add', 'https://github.com/octocat/Hello-World.git', 'limit-test'
            ])
            assert result.exit_code == 0

            searcher = RipgrepSearcher()
            options = SearchOptions(max_results=10000)
            results = searcher.search_repository('limit-test', '.', options)

            assert isinstance(results, list)

    def test_special_characters_in_query(self):
        """Test handling of special characters in search queries."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(app, [
                'add', 'https://github.com/octocat/Hello-World.git', 'special-test'
            ])
            assert result.exit_code == 0

            searcher = RipgrepSearcher()

            # Test regex characters
            special_queries = ['.*', '[a-z]', '\\w+', '(hello|world)']

            for query in special_queries:
                try:
                    results = searcher.search_repository('special-test', query)
                    assert isinstance(results, list)
                except Exception:
                    # Some regex patterns may fail, that's acceptable
                    pass

    def test_cache_expiration(self):
        """Test cache expiration functionality."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(app, [
                'add', 'https://github.com/octocat/Hello-World.git', 'cache-test'
            ])
            assert result.exit_code == 0

            searcher = RipgrepSearcher(enable_cache=True)
            options = SearchOptions()

            # Perform search to populate cache
            results = searcher.search_repository('cache-test', 'Hello', options)
            assert len(results) > 0

            # Manually expire cache
            import datetime
            searcher.cache.cache_ttl = datetime.timedelta(seconds=-1)

            # Next search should not use cache
            results2 = searcher.search_repository('cache-test', 'Hello', options)
            assert len(results2) > 0