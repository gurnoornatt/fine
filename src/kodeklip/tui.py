"""
Interactive TUI for KodeKlip search results using Textual framework.

This module provides a two-pane terminal interface for browsing search results,
previewing files with syntax highlighting, and copying code to clipboard.
"""

from pathlib import Path
from typing import Any

import pyperclip
from rich.syntax import Syntax
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import (
    DataTable,
    Header,
    RichLog,
    Static,
)

from .search import SearchResult


class SearchResultsTable(DataTable):
    """DataTable widget for displaying search results with selection tracking."""

    def __init__(self, results: list[SearchResult], **kwargs: Any) -> None:
        """Initialize with search results."""
        super().__init__(**kwargs)
        self.results = results
        self.selected_rows: set[int] = set()  # Use regular set instead of reactive
        self.cursor_type = "row"
        self.zebra_stripes = True
        self.show_header = True

    def on_mount(self) -> None:
        """Set up the table when mounted."""
        # Add columns
        self.add_columns("", "File", "Line", "Content")

        # Add data rows
        for i, result in enumerate(self.results):
            # Truncate long content for table display
            content = result.line_content.strip()
            if len(content) > 60:
                content = content[:57] + "..."

            self.add_row(
                "",  # Selection indicator
                result.file_path,
                str(result.line_number),
                content,
                key=str(i)
            )

    def toggle_row_selection(self, row_index: int) -> None:
        """Toggle selection state of a row."""
        if row_index in self.selected_rows:
            self.selected_rows.remove(row_index)
            # Use string key as set in add_row
            try:
                self.update_cell(str(row_index), "0", "")  # Use string for column key
            except Exception:
                # If cells don't exist yet (e.g., in tests), just track selection
                pass
        else:
            self.selected_rows.add(row_index)
            try:
                self.update_cell(str(row_index), "0", "✓")  # Use string for column key
            except Exception:
                # If cells don't exist yet (e.g., in tests), just track selection
                pass

    def get_selected_results(self) -> list[SearchResult]:
        """Get currently selected search results."""
        return [self.results[i] for i in self.selected_rows]

    def get_current_result(self) -> SearchResult | None:
        """Get the currently highlighted result."""
        if self.cursor_row >= 0 and self.cursor_row < len(self.results):
            return self.results[self.cursor_row]
        return None


class FilePreview(RichLog):
    """RichLog widget for displaying file previews with syntax highlighting."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the file preview."""
        super().__init__(**kwargs)
        self.auto_scroll = False
        self.highlight = True
        self.markup = False

    def show_result(self, result: SearchResult, repo_path: str) -> None:
        """Display a search result with context and syntax highlighting."""
        self.clear()

        try:
            # Construct full file path
            full_path = Path(repo_path) / result.file_path

            if not full_path.exists():
                self.write(f"[red]File not found: {full_path}[/red]")
                return

            # Read file content
            content = full_path.read_text(encoding='utf-8', errors='replace')
            lines = content.splitlines()

            # Calculate context window
            context_lines = 10
            start_line = max(0, result.line_number - context_lines - 1)
            end_line = min(len(lines), result.line_number + context_lines)

            # Extract context
            context_content = lines[start_line:end_line]

            # Create syntax highlighted preview
            language = self._detect_language(result.file_path)
            if language and context_content:
                syntax = Syntax(
                    '\n'.join(context_content),
                    language,
                    line_numbers=True,
                    start_line=start_line + 1,
                    highlight_lines={result.line_number}
                )
                self.write(syntax)
            else:
                # Fallback to plain text with line numbers
                for i, line in enumerate(context_content, start=start_line + 1):
                    marker = ">>> " if i == result.line_number else "    "
                    self.write(f"{marker}{i:4d}: {line}")

        except Exception as e:
            self.write(f"[red]Error reading file: {str(e)}[/red]")

    def _detect_language(self, file_path: str) -> str | None:
        """Detect programming language from file extension."""
        ext_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'jsx',
            '.tsx': 'tsx',
            '.rs': 'rust',
            '.go': 'go',
            '.java': 'java',
            '.c': 'c',
            '.cpp': 'cpp',
            '.cc': 'cpp',
            '.cxx': 'cpp',
            '.h': 'c',
            '.hpp': 'cpp',
            '.md': 'markdown',
            '.json': 'json',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.xml': 'xml',
            '.html': 'html',
            '.css': 'css',
            '.sql': 'sql',
            '.sh': 'bash',
            '.bash': 'bash',
            '.zsh': 'zsh',
            '.php': 'php',
            '.rb': 'ruby',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
        }

        path = Path(file_path)
        return ext_map.get(path.suffix.lower())


class StatusBar(Static):
    """Status bar showing current selection and keyboard shortcuts."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize status bar."""
        super().__init__(**kwargs)
        self.update_status(0, 0, 0)

    def update_status(self, selected_count: int, current_index: int, total_count: int) -> None:
        """Update the status bar with current selection info."""
        if total_count == 0:
            status_text = "No results"
        else:
            status_text = f"Selected: {selected_count} | Current: {current_index + 1}/{total_count}"

        shortcuts = "j/k:Navigate | Space:Select | c:Copy | y:Yank Line | Enter:View Full | q:Quit"

        self.update(f"[bold]{status_text}[/bold] | {shortcuts}")


class SearchApp(App):
    """Main Textual app for interactive search results browsing."""

    TITLE = "KodeKlip - Interactive Search"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("j", "next_result", "Next"),
        ("k", "prev_result", "Previous"),
        ("space", "toggle_selection", "Toggle Selection"),
        ("c", "copy_selected", "Copy Selected"),
        ("y", "yank_current", "Yank Current"),
        ("enter", "view_full_file", "View Full File"),
        ("escape", "quit", "Quit"),
    ]

    CSS = """
    Screen {
        layout: grid;
        grid-columns: 1fr 1fr;
        grid-rows: auto 1fr auto;
        grid-gutter: 1;
    }

    Header {
        column-span: 2;
        height: 3;
    }

    .left-pane {
        border: solid $accent;
        border-title-align: center;
    }

    .right-pane {
        border: solid $accent;
        border-title-align: center;
    }

    StatusBar {
        column-span: 2;
        height: 1;
        background: $surface;
        color: $text;
        padding: 0 1;
    }

    DataTable {
        height: 100%;
    }

    RichLog {
        height: 100%;
    }
    """

    def __init__(self, results: list[SearchResult], query: str, repo_path: str, **kwargs: Any) -> None:
        """Initialize the search app."""
        super().__init__(**kwargs)
        self.results = results
        self.search_query = query  # Renamed to avoid conflict with App.query method
        self.repo_path = repo_path

    def compose(self) -> ComposeResult:
        """Create the app layout."""
        yield Header(show_clock=True)

        with Container(classes="left-pane"):
            yield SearchResultsTable(self.results, id="results-table")

        with Container(classes="right-pane"):
            yield FilePreview(id="file-preview")

        yield StatusBar(id="status-bar")

    def on_mount(self) -> None:
        """Set up the app when mounted."""
        self.title = f"KodeKlip - Search: '{self.search_query}'"

        # Border titles are set via CSS instead

        self.update_preview()
        self.update_status()

    def on_data_table_row_highlighted(self, _event: DataTable.RowHighlighted) -> None:
        """Handle row selection changes."""
        self.update_preview()
        self.update_status()

    def update_preview(self) -> None:
        """Update the file preview pane."""
        table = self.query_one("#results-table", SearchResultsTable)
        preview = self.query_one("#file-preview", FilePreview)

        current_result = table.get_current_result()
        if current_result:
            preview.show_result(current_result, self.repo_path)

    def update_status(self) -> None:
        """Update the status bar."""
        table = self.query_one("#results-table", SearchResultsTable)
        status_bar = self.query_one("#status-bar", StatusBar)

        selected_count = len(table.selected_rows)
        current_index = table.cursor_row
        total_count = len(self.results)

        status_bar.update_status(selected_count, current_index, total_count)

    def action_next_result(self) -> None:
        """Move to next result."""
        table = self.query_one("#results-table", SearchResultsTable)
        table.action_cursor_down()

    def action_prev_result(self) -> None:
        """Move to previous result."""
        table = self.query_one("#results-table", SearchResultsTable)
        table.action_cursor_up()

    def action_toggle_selection(self) -> None:
        """Toggle selection of current row."""
        table = self.query_one("#results-table", SearchResultsTable)
        table.toggle_row_selection(table.cursor_row)
        self.update_status()

    def action_copy_selected(self) -> None:
        """Copy selected results to clipboard."""
        table = self.query_one("#results-table", SearchResultsTable)
        selected_results = table.get_selected_results()

        if not selected_results:
            self.notify("No results selected", severity="warning")
            return

        # Format results for clipboard
        clipboard_content = self._format_results_for_clipboard(selected_results)

        try:
            pyperclip.copy(clipboard_content)
            count = len(selected_results)
            self.notify(f"Copied {count} result{'s' if count > 1 else ''} to clipboard", severity="information")
        except Exception as e:
            self.notify(f"Failed to copy to clipboard: {str(e)}", severity="error")

    def action_yank_current(self) -> None:
        """Copy current line to clipboard."""
        table = self.query_one("#results-table", SearchResultsTable)
        current_result = table.get_current_result()

        if not current_result:
            self.notify("No result selected", severity="warning")
            return

        try:
            pyperclip.copy(current_result.line_content.strip())
            self.notify("Yanked current line to clipboard", severity="information")
        except Exception as e:
            self.notify(f"Failed to copy to clipboard: {str(e)}", severity="error")

    def action_view_full_file(self) -> None:
        """View full file (placeholder - could open in editor)."""
        table = self.query_one("#results-table", SearchResultsTable)
        current_result = table.get_current_result()

        if current_result:
            full_path = Path(self.repo_path) / current_result.file_path
            self.notify(f"Full path: {full_path}", severity="information")

    def _format_results_for_clipboard(self, results: list[SearchResult]) -> str:
        """Format search results for clipboard copying."""
        lines = [
            f"# KodeKlip Search Results: '{self.search_query}'",
            f"# {len(results)} result{'s' if len(results) > 1 else ''}",
            "",
        ]

        for result in results:
            lines.extend([
                f"## {result.file_path}:{result.line_number}",
                "```",
                result.line_content.strip(),
                "```",
                "",
            ])

        return "\n".join(lines)


def launch_interactive_search(results: list[SearchResult], query: str, repo_path: str) -> None:
    """Launch the interactive TUI for search results."""
    if not results:
        print("No results to display interactively")
        return

    app = SearchApp(results, query, repo_path)
    app.run()
