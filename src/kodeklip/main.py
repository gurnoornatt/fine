"""
KodeKlip CLI - Main entry point for the application.

This module defines the command-line interface using Typer.
"""

from typing import Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

# Create the main Typer application
app = typer.Typer(
    name="kodeklip",
    help="🔪 KodeKlip - Surgical Code Context Management Tool\n\n"
    "Fight context bloat with precision code extraction for LLM interactions.",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Initialize Rich console for beautiful output
console = Console()


def version_callback(value: bool) -> None:
    """Show version information."""
    if value:
        from . import __version__

        rprint(
            f"[bold blue]KodeKlip[/bold blue] version [green]{__version__}[/green]"
        )
        raise typer.Exit()


@app.callback()
def main(
    _version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    )
) -> None:
    """
    🔪 KodeKlip - Surgical Code Context Management Tool

    Fight context bloat with precision code extraction for LLM interactions.

    Use CLIs instead of MCPs for better control over your context window!
    """
    pass


@app.command()
def add(
    repo_url: str = typer.Argument(
        ..., help="Repository URL to clone (GitHub, GitLab, etc.)"
    ),
    alias: Optional[str] = typer.Argument(
        None, help="Alias for the repository (auto-generated if not provided)"
    ),
) -> None:
    """
    📦 Add a repository to your local knowledge base.

    Clone a repository and add it to KodeKlip's local cache for instant searching.

    Examples:
        kk add https://github.com/python/cpython python
        kk add https://github.com/tiangolo/fastapi
    """
    if not alias:
        # Generate alias from repo URL
        alias = repo_url.split("/")[-1].replace(".git", "")

    console.print(f"[yellow]📦 Adding repository:[/yellow] {repo_url}")
    console.print(f"[blue]🏷️  Alias:[/blue] {alias}")
    console.print("[red]⚠️  Not implemented yet - this is a placeholder command[/red]")


@app.command()
def list() -> None:
    """
    📋 List all repositories in your knowledge base.

    Shows status, last updated time, and indexing information.
    """
    console.print("[yellow]📋 Repository Knowledge Base[/yellow]")

    # Create a sample table showing what the output will look like
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Alias", style="cyan", no_wrap=True)
    table.add_column("URL", style="blue")
    table.add_column("Status", justify="center")
    table.add_column("Last Updated", style="green")
    table.add_column("Indexed", justify="center")

    # Sample data to show expected format
    table.add_row(
        "python",
        "https://github.com/python/cpython",
        "✅ Ready",
        "2025-01-15",
        "🔍 Yes",
    )
    table.add_row(
        "fastapi",
        "https://github.com/tiangolo/fastapi",
        "⏳ Cloning",
        "2025-01-15",
        "❌ No",
    )

    console.print(table)
    console.print("[red]⚠️  Sample data shown - actual implementation pending[/red]")


@app.command()
def update(
    alias: Optional[str] = typer.Argument(
        None, help="Repository alias to update (all if not specified)"
    ),
    all_repos: bool = typer.Option(False, "--all", help="Update all repositories"),
) -> None:
    """
    🔄 Update repositories with latest changes.

    Pull the latest changes from remote repositories.

    Examples:
        kk update python      # Update specific repo
        kk update --all       # Update all repos
    """
    if all_repos or not alias:
        console.print("[yellow]🔄 Updating all repositories...[/yellow]")
    else:
        console.print(f"[yellow]🔄 Updating repository:[/yellow] {alias}")

    console.print("[red]⚠️  Not implemented yet - this is a placeholder command[/red]")


@app.command()
def find(
    alias: str = typer.Argument(..., help="Repository alias to search in"),
    query: str = typer.Argument(..., help="Search query or pattern"),
    interactive: bool = typer.Option(
        False, "-i", "--interactive", help="Launch interactive TUI"
    ),
    file_type: Optional[str] = typer.Option(
        None, "-t", "--type", help="Filter by file type (e.g., py, js, rs)"
    ),
    context: int = typer.Option(
        0, "-c", "--context", help="Show context lines around matches"
    ),
    semantic: bool = typer.Option(
        False, "-s", "--semantic", help="Use semantic search instead of keyword search"
    ),
    limit: int = typer.Option(50, "--limit", help="Maximum number of results to show"),
) -> None:
    """
    🔍 Search for code patterns in a repository.

    Perform lightning-fast searches using ripgrep with optional interactive TUI.

    Examples:
        kk find python "async def"           # Basic search
        kk find python "database" -i        # Interactive mode
        kk find python "connection" -t py   # Filter Python files
        kk find python "auth" -s           # Semantic search
    """
    console.print(f"[yellow]🔍 Searching in:[/yellow] {alias}")
    console.print(f"[blue]📝 Query:[/blue] '{query}'")

    if semantic:
        console.print("[purple]🧠 Using semantic search[/purple]")
    else:
        console.print("[cyan]⚡ Using keyword search (ripgrep)[/cyan]")

    if interactive:
        console.print("[green]🖥️  Launching interactive TUI...[/green]")

    if file_type:
        console.print(f"[magenta]📁 File type filter:[/magenta] {file_type}")

    if context > 0:
        console.print(f"[dim]📄 Context lines:[/dim] {context}")

    console.print(f"[dim]🔢 Result limit:[/dim] {limit}")
    console.print("[red]⚠️  Not implemented yet - this is a placeholder command[/red]")


@app.command()
def index(
    alias: str = typer.Argument(..., help="Repository alias to index"),
    force: bool = typer.Option(
        False, "--force", help="Force re-indexing even if already indexed"
    ),
) -> None:
    """
    🗂️  Index a repository for semantic search.

    Process repository files to enable intelligent semantic search capabilities.

    Examples:
        kk index python         # Index the python repo
        kk index python --force # Force re-indexing
    """
    console.print(f"[yellow]🗂️  Indexing repository:[/yellow] {alias}")

    if force:
        console.print("[orange1]🔄 Force re-indexing enabled[/orange1]")

    console.print(
        "[purple]🧠 Building semantic index with tree-sitter + FAISS...[/purple]"
    )
    console.print("[red]⚠️  Not implemented yet - this is a placeholder command[/red]")


@app.command()
def remove(
    alias: str = typer.Argument(..., help="Repository alias to remove"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation prompt"),
) -> None:
    """
    🗑️  Remove a repository from knowledge base.

    Delete the local repository cache and all associated indices.

    Examples:
        kk remove old-repo       # Remove with confirmation
        kk remove old-repo --force  # Remove without confirmation
    """
    if not force:
        confirm = typer.confirm(f"Are you sure you want to remove '{alias}'?")
        if not confirm:
            console.print("[blue]ℹ️  Operation cancelled[/blue]")
            raise typer.Exit()

    console.print(f"[red]🗑️  Removing repository:[/red] {alias}")
    console.print("[red]⚠️  Not implemented yet - this is a placeholder command[/red]")


if __name__ == "__main__":
    app()
