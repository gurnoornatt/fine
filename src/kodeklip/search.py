"""
Search functionality for KodeKlip using ripgrep integration.

This module provides fast keyword search capabilities using ripgrepy
Python wrapper for structured ripgrep operations.
"""

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Union

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from ripgrepy import Ripgrepy
from sqlmodel import Session, select

from .database import get_engine
from .models import Repository


@dataclass
class SearchResult:
    """Structured search result from ripgrep."""

    file_path: str
    line_number: int
    line_content: str
    match_start: int = 0
    match_end: int = 0
    context_before: list[str] = field(default_factory=list)
    context_after: list[str] = field(default_factory=list)

    @property
    def relative_path(self) -> str:
        """Get relative path for display."""
        return self.file_path

    @property
    def file_extension(self) -> str:
        """Get file extension for syntax highlighting."""
        return Path(self.file_path).suffix.lstrip('.')

    def __str__(self) -> str:
        """String representation for display."""
        return f"{self.file_path}:{self.line_number}: {self.line_content.strip()}"

    def to_rich_panel(
        self, console: Console, highlight_query: str | None = None
    ) -> Panel:
        """Create a rich panel for this search result."""
        # Create syntax highlighted content
        language = self._get_language_for_extension()

        content_lines = []
        if self.context_before:
            content_lines.extend(self.context_before)
        content_lines.append(self.line_content)
        if self.context_after:
            content_lines.extend(self.context_after)

        content = '\n'.join(content_lines)

        renderable: Union[Syntax, Text]
        if language:
            renderable = Syntax(
                content,
                language,
                line_numbers=True,
                start_line=max(1, self.line_number - len(self.context_before))
            )
        else:
            renderable = Text(content)

        # Create title with file info
        title = (
            f"[bold blue]{self.file_path}[/bold blue]:"
            f"[bold yellow]{self.line_number}[/bold yellow]"
        )

        return Panel(renderable, title=title, border_style="cyan")

    def _get_language_for_extension(self) -> str | None:
        """Map file extension to syntax highlighting language."""
        ext_map = {
            'py': 'python',
            'js': 'javascript',
            'ts': 'typescript',
            'rs': 'rust',
            'go': 'go',
            'java': 'java',
            'c': 'c',
            'cpp': 'cpp',
            'h': 'c',
            'hpp': 'cpp',
            'md': 'markdown',
            'json': 'json',
            'yaml': 'yaml',
            'yml': 'yaml',
            'xml': 'xml',
            'html': 'html',
            'css': 'css',
            'sql': 'sql',
            'sh': 'bash',
            'bash': 'bash',
        }
        return ext_map.get(self.file_extension.lower())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'file_path': self.file_path,
            'line_number': self.line_number,
            'line_content': self.line_content,
            'match_start': self.match_start,
            'match_end': self.match_end,
            'context_before': self.context_before,
            'context_after': self.context_after,
        }


@dataclass
class SearchOptions:
    """Configuration options for search operations."""

    file_types: list[str] = field(default_factory=list)
    exclude_types: list[str] = field(default_factory=list)
    context_before: int = 0
    context_after: int = 0
    ignore_case: bool = False
    smart_case: bool = True
    regex_mode: bool = True
    max_results: int = 1000
    include_patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)


@dataclass
class SearchCache:
    """Simple in-memory cache for search results."""

    cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    cache_ttl: timedelta = field(default_factory=lambda: timedelta(minutes=10))

    def _make_key(self, repo_alias: str, query: str, options: SearchOptions) -> str:
        """Create cache key from search parameters."""
        options_dict = {
            'file_types': sorted(options.file_types),
            'exclude_types': sorted(options.exclude_types),
            'context_before': options.context_before,
            'context_after': options.context_after,
            'ignore_case': options.ignore_case,
            'smart_case': options.smart_case,
            'regex_mode': options.regex_mode,
            'max_results': options.max_results,
            'include_patterns': sorted(options.include_patterns),
            'exclude_patterns': sorted(options.exclude_patterns),
        }
        key_data = f"{repo_alias}:{query}:{json.dumps(options_dict, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def get(
        self, repo_alias: str, query: str, options: SearchOptions
    ) -> list[SearchResult] | None:
        """Get cached results if still valid."""
        key = self._make_key(repo_alias, query, options)
        if key in self.cache:
            entry = self.cache[key]
            if datetime.now() - entry['timestamp'] < self.cache_ttl:
                # Reconstruct SearchResult objects
                return [SearchResult(**result) for result in entry['results']]
            else:
                # Cache expired
                del self.cache[key]
        return None

    def set(
        self,
        repo_alias: str,
        query: str,
        options: SearchOptions,
        results: list[SearchResult],
    ) -> None:
        """Cache search results."""
        key = self._make_key(repo_alias, query, options)
        self.cache[key] = {
            'timestamp': datetime.now(),
            'results': [result.to_dict() for result in results]
        }

    def clear(self) -> None:
        """Clear all cached results."""
        self.cache.clear()


class SearchResultFormatter:
    """Rich formatting for search results."""

    def __init__(self, console: Console | None = None):
        """Initialize formatter with optional console."""
        self.console = console or Console()

    def format_results_table(
        self, results: list[SearchResult], query: str = ""
    ) -> Table:
        """Format search results as a rich table."""
        table = Table(title=f"Search Results: '{query}'" if query else "Search Results")
        table.add_column("File", style="cyan", no_wrap=True)
        table.add_column("Line", style="magenta", justify="right")
        table.add_column("Content", style="white")

        for result in results:
            # Truncate long content
            content = result.line_content.strip()
            if len(content) > 80:
                content = content[:77] + "..."

            table.add_row(
                result.file_path,
                str(result.line_number),
                content
            )

        return table

    def format_results_detailed(
        self, results: list[SearchResult], query: str = ""
    ) -> list[Panel]:
        """Format search results as detailed panels."""
        panels = []
        for result in results[:10]:  # Limit to first 10 for detailed view
            panels.append(result.to_rich_panel(self.console, query))
        return panels

    def format_summary(
        self, results_dict: dict[str, list[SearchResult]], query: str = ""
    ) -> Panel:
        """Format a summary of multi-repository search results."""
        summary_table = Table()
        summary_table.add_column("Repository", style="cyan")
        summary_table.add_column("Matches", style="green", justify="right")

        total_results = 0
        for repo, results in results_dict.items():
            count = len(results)
            total_results += count
            summary_table.add_row(repo, str(count))

        title = f"Search Summary: '{query}' ({total_results} total matches)"
        return Panel(summary_table, title=title, border_style="green")


class RipgrepSearcher:
    """Fast search functionality using ripgrep."""

    def __init__(self, rg_path: str | None = None, enable_cache: bool = True):
        """
        Initialize RipgrepSearcher.

        Args:
            rg_path: Optional path to ripgrep binary. If None, will attempt to detect.
            enable_cache: Whether to enable result caching.
        """
        self.rg_path = self._detect_ripgrep_path() if rg_path is None else rg_path
        if not self.rg_path:
            raise RuntimeError(
                "ripgrep binary not found. Please install ripgrep: "
                "https://github.com/BurntSushi/ripgrep#installation"
            )
        self.cache = SearchCache() if enable_cache else None
        self.formatter = SearchResultFormatter()

    def _detect_ripgrep_path(self) -> str | None:
        """Detect ripgrep binary path with fallbacks."""
        # Try common locations and aliases
        candidates = [
            'rg',  # In PATH
            '/usr/local/bin/rg',  # Homebrew
            '/opt/homebrew/bin/rg',  # M1 Homebrew
            # Claude Code
            '/opt/homebrew/lib/node_modules/@anthropic-ai/claude-code/'
            'vendor/ripgrep/arm64-darwin/rg',
        ]

        for candidate in candidates:
            if shutil.which(candidate):
                return candidate

        # Check if we can resolve the aliased version
        import subprocess
        try:
            result = subprocess.run(['which', 'rg'], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass

        return None

    def validate_ripgrep(self) -> bool:
        """Validate that ripgrep is working correctly."""
        try:
            # Just test that we can create the object - don't run a search
            Ripgrepy('test', '.', rg_path=self.rg_path)
            return True
        except Exception:
            return False

    def search_repository(
        self,
        alias: str,
        query: str,
        options: SearchOptions | None = None
    ) -> list[SearchResult]:
        """
        Search for a query within a repository.

        Args:
            alias: Repository alias to search in
            query: Search query/pattern
            options: Optional search configuration

        Returns:
            List of SearchResult objects

        Raises:
            ValueError: If repository not found or invalid
            RuntimeError: If search operation fails
        """
        if options is None:
            options = SearchOptions()

        # Check cache first
        if self.cache:
            cached_results = self.cache.get(alias, query, options)
            if cached_results is not None:
                return cached_results

        # Get repository from database
        engine = get_engine()
        with Session(engine) as session:
            statement = select(Repository).where(Repository.alias == alias)
            repo = session.exec(statement).first()

            if not repo:
                raise ValueError(f"Repository '{alias}' not found")

            repo_path = Path(repo.local_path)
            if not repo_path.exists():
                raise ValueError(f"Repository path does not exist: {repo_path}")

        # Execute ripgrep search
        try:
            results = self._execute_search(str(repo_path), query, options)

            # Cache results
            if self.cache:
                self.cache.set(alias, query, options, results)

            return results
        except Exception as e:
            raise RuntimeError(f"Search failed: {str(e)}") from e

    def _execute_search(
        self,
        repo_path: str,
        query: str,
        options: SearchOptions
    ) -> list[SearchResult]:
        """Execute the actual ripgrep search."""
        # Create ripgrepy instance
        rg = Ripgrepy(query, repo_path, rg_path=self.rg_path)

        # Configure search options
        rg = rg.with_filename().line_number()

        # File type filters
        for file_type in options.file_types:
            rg = rg.type_(file_type)
        for exclude_type in options.exclude_types:
            rg = rg.type_not(exclude_type)

        # Include/exclude patterns
        for pattern in options.include_patterns:
            rg = rg.glob(pattern)
        for pattern in options.exclude_patterns:
            rg = rg.glob(f"!{pattern}")

        # Context lines
        if options.context_before > 0:
            rg = rg.before_context(options.context_before)
        if options.context_after > 0:
            rg = rg.after_context(options.context_after)

        # Case sensitivity
        if options.ignore_case:
            rg = rg.ignore_case()
        elif options.smart_case:
            rg = rg.smart_case()

        # Limit results
        rg = rg.max_count(options.max_results)

        # Execute search
        result = rg.run()

        # Parse results
        return self._parse_ripgrep_results(result.as_string, repo_path)

    def _parse_ripgrep_results(self, output: str, repo_path: str) -> list[SearchResult]:
        """Parse ripgrep output into SearchResult objects."""
        results = []
        repo_path_obj = Path(repo_path)

        for line in output.splitlines():
            if not line.strip():
                continue

            # Parse ripgrep output format: file:line:content
            parts = line.split(':', 2)
            if len(parts) < 3:
                continue

            try:
                file_path = parts[0]
                line_number = int(parts[1])
                line_content = parts[2]

                # Make path relative to repo
                abs_file_path = Path(file_path)
                if abs_file_path.is_absolute():
                    try:
                        relative_path = abs_file_path.relative_to(repo_path_obj)
                        file_path = str(relative_path)
                    except ValueError:
                        # Path is not relative to repo_path, keep as-is
                        pass

                result = SearchResult(
                    file_path=file_path,
                    line_number=line_number,
                    line_content=line_content
                )
                results.append(result)

            except (ValueError, IndexError):
                # Skip malformed lines
                continue

        return results

    def search_all_repositories(
        self,
        query: str,
        options: SearchOptions | None = None
    ) -> dict[str, list[SearchResult]]:
        """
        Search across all managed repositories.

        Args:
            query: Search query/pattern
            options: Optional search configuration

        Returns:
            Dict mapping repository alias to search results
        """
        if options is None:
            options = SearchOptions()

        results = {}
        engine = get_engine()

        with Session(engine) as session:
            statement = select(Repository)
            repositories = session.exec(statement).all()

            for repo in repositories:
                try:
                    repo_results = self.search_repository(repo.alias, query, options)
                    if repo_results:  # Only include repos with results
                        results[repo.alias] = repo_results
                except Exception:
                    # Skip repositories that fail to search
                    continue

        return results


def create_searcher() -> RipgrepSearcher:
    """Factory function to create a configured RipgrepSearcher."""
    return RipgrepSearcher()
