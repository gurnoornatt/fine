"""
KodeKlip CLI - Main entry point for the application.

This module defines the command-line interface using Typer.
"""

from datetime import datetime
from typing import Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.progress import track
from rich.table import Table

from .database import create_db_and_tables
from .git_manager import GitRepository

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

        rprint(f"[bold blue]KodeKlip[/bold blue] version [green]{__version__}[/green]")
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
    try:
        # Initialize database if it doesn't exist
        create_db_and_tables()

        # Initialize git manager
        git_manager = GitRepository()

        # Validate repository URL
        if not git_manager.validate_repository_url(repo_url):
            console.print(f"[red]❌ Invalid repository URL:[/red] {repo_url}")
            console.print(
                "[dim]Supported formats: GitHub, GitLab, Bitbucket URLs[/dim]"
            )
            raise typer.Exit(1)

        # Generate alias if not provided
        if not alias:
            alias = repo_url.split("/")[-1].replace(".git", "")

        # Validate alias format (alphanumeric + hyphens)
        if not alias.replace("-", "").replace("_", "").isalnum():
            console.print(f"[red]❌ Invalid alias:[/red] {alias}")
            console.print(
                "[dim]Alias must contain only letters, numbers, hyphens, and underscores[/dim]"
            )
            raise typer.Exit(1)

        console.print(f"[yellow]📦 Adding repository:[/yellow] {repo_url}")
        console.print(f"[blue]🏷️  Alias:[/blue] {alias}")

        # Check if repository already exists
        if git_manager.repository_exists(alias):
            console.print(f"[red]❌ Repository with alias '{alias}' already exists[/red]")
            raise typer.Exit(1)

        # Clone repository with progress indication
        success, message, repo_record = git_manager.clone_repository(repo_url, alias)

        if success:
            console.print(f"[green]✅ {message}[/green]")
            if repo_record:
                console.print(f"[dim]📁 Local path: {repo_record.local_path}[/dim]")
        else:
            console.print(f"[red]❌ Failed to add repository:[/red] {message}")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]❌ Unexpected error:[/red] {str(e)}")
        raise typer.Exit(1) from e


@app.command()
def list(
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format")
) -> None:
    """
    📋 List all repositories in your knowledge base.

    Shows status, last updated time, and indexing information.
    """
    try:
        # Initialize database if it doesn't exist
        create_db_and_tables()

        # Initialize git manager
        git_manager = GitRepository()

        # Get all repositories
        repositories = git_manager.list_repositories()

        if not repositories:
            console.print("[yellow]📋 No repositories found in knowledge base[/yellow]")
            console.print("[dim]💡 Add your first repository with: kk add <repo-url>[/dim]")
            return

        if json_output:
            import json
            repo_data = []
            for repo in repositories:
                repo_data.append({
                    "alias": repo.alias,
                    "url": repo.url,
                    "local_path": repo.local_path,
                    "last_updated": repo.last_updated.isoformat() if repo.last_updated else None,
                    "indexed": repo.indexed
                })
            print(json.dumps(repo_data, indent=2))
            return

        console.print("[yellow]📋 Repository Knowledge Base[/yellow]")

        # Get disk usage information
        _, _, usage_info = git_manager.get_disk_usage()

        # Create table with real data
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Alias", style="cyan", no_wrap=True)
        table.add_column("URL", style="blue", max_width=50)
        table.add_column("Status", justify="center")
        table.add_column("Last Updated", style="green")
        table.add_column("Size", justify="right", style="yellow")
        table.add_column("Indexed", justify="center")

        for repo in repositories:
            # Determine status
            if git_manager.repository_exists(repo.alias):
                status = "[green]✅ Ready[/green]"
            else:
                status = "[red]❌ Missing[/red]"

            # Format last updated
            if repo.last_updated:
                # Calculate relative time
                now = datetime.utcnow()
                diff = now - repo.last_updated
                if diff.days > 0:
                    last_updated = f"{diff.days}d ago"
                elif diff.seconds > 3600:
                    hours = diff.seconds // 3600
                    last_updated = f"{hours}h ago"
                elif diff.seconds > 60:
                    minutes = diff.seconds // 60
                    last_updated = f"{minutes}m ago"
                else:
                    last_updated = "Just now"
            else:
                last_updated = "[dim]Never[/dim]"

            # Format size
            if repo.alias in usage_info.get("repo_sizes", {}):
                size_mb = usage_info["repo_sizes"][repo.alias]
                if size_mb >= 1000:
                    size = f"{size_mb/1000:.1f} GB"
                else:
                    size = f"{size_mb:.1f} MB"
            else:
                size = "[dim]Unknown[/dim]"

            # Format indexed status
            indexed_status = "[green]🔍 Yes[/green]" if repo.indexed else "[dim]❌ No[/dim]"

            table.add_row(
                repo.alias,
                repo.url,
                status,
                last_updated,
                size,
                indexed_status
            )

        console.print(table)

        # Show summary
        total_count = len(repositories)
        indexed_count = sum(1 for repo in repositories if repo.indexed)
        total_size = usage_info.get("total_size_mb", 0)

        console.print()
        console.print(
            f"[dim]📊 {total_count} repositories • "
            f"{indexed_count} indexed • {total_size:.1f} MB total[/dim]"
        )

    except Exception as e:
        console.print(f"[red]❌ Error listing repositories:[/red] {str(e)}")
        raise typer.Exit(1) from e


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
    try:
        # Initialize database if it doesn't exist
        create_db_and_tables()

        # Initialize git manager
        git_manager = GitRepository()

        # Determine which repositories to update
        if all_repos or not alias:
            repositories = git_manager.list_repositories()
            if not repositories:
                console.print("[yellow]📋 No repositories found to update[/yellow]")
                return
            console.print(f"[yellow]🔄 Updating {len(repositories)} repositories...[/yellow]")
            aliases_to_update = [repo.alias for repo in repositories]
        else:
            # Validate that specific repository exists
            if not git_manager.repository_exists(alias):
                console.print(f"[red]❌ Repository '{alias}' not found[/red]")
                console.print("[dim]💡 Use 'kk list' to see available repositories[/dim]")
                raise typer.Exit(1)
            aliases_to_update = [alias]
            console.print(f"[yellow]🔄 Updating repository:[/yellow] {alias}")

        updated_count = 0
        unchanged_count = 0
        error_count = 0

        # Update each repository
        for repo_alias in track(aliases_to_update, description="Updating repositories..."):
            success, message, has_changes = git_manager.update_repository(repo_alias)

            if success:
                if has_changes:
                    console.print(f"[green]✅ {repo_alias}:[/green] {message}")
                    updated_count += 1
                else:
                    console.print(f"[dim]ℹ️  {repo_alias}: {message}[/dim]")
                    unchanged_count += 1
            else:
                console.print(f"[red]❌ {repo_alias}:[/red] {message}")
                error_count += 1

        # Show summary
        console.print()
        if len(aliases_to_update) > 1:
            console.print(
                f"[green]📊 Update complete:[/green] {updated_count} updated, "
                f"{unchanged_count} up-to-date, {error_count} errors"
            )

        if error_count > 0:
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]❌ Error updating repositories:[/red] {str(e)}")
        raise typer.Exit(1) from e


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
    keep_files: bool = typer.Option(False, "--keep-files", help="Keep local files, only remove from database"),
) -> None:
    """
    🗑️  Remove a repository from knowledge base.

    Delete the local repository cache and all associated indices.

    Examples:
        kk remove old-repo       # Remove with confirmation
        kk remove old-repo --force  # Remove without confirmation
        kk remove old-repo --keep-files  # Keep files, remove from database only
    """
    try:
        # Initialize database if it doesn't exist
        create_db_and_tables()

        # Initialize git manager
        git_manager = GitRepository()

        # Check if repository exists
        if not git_manager.repository_exists(alias):
            console.print(f"[red]❌ Repository '{alias}' not found[/red]")
            console.print("[dim]💡 Use 'kk list' to see available repositories[/dim]")
            raise typer.Exit(1)

        # Get repository info for confirmation
        repo_info = git_manager.get_repository_info(alias)
        if repo_info:
            console.print(f"[yellow]🗑️  Repository to remove:[/yellow] {alias}")
            console.print(f"[dim]📂 URL: {repo_info.url}[/dim]")
            console.print(f"[dim]📁 Local path: {repo_info.local_path}[/dim]")

        # Confirmation prompt unless --force
        if not force:
            action = "remove from database only" if keep_files else "completely remove"
            confirm = typer.confirm(f"Are you sure you want to {action} '{alias}'?")
            if not confirm:
                console.print("[blue]ℹ️  Operation cancelled[/blue]")
                raise typer.Exit()

        # Remove repository
        success, message = git_manager.remove_repository(alias, keep_files=keep_files)

        if success:
            console.print(f"[green]✅ {message}[/green]")
        else:
            console.print(f"[red]❌ Failed to remove repository:[/red] {message}")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]❌ Error removing repository:[/red] {str(e)}")
        raise typer.Exit(1) from e


if __name__ == "__main__":
    app()
