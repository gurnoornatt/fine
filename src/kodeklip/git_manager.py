"""
Git repository management for KodeKlip.

This module provides GitRepository class for managing git operations
including cloning, updating, and removing repositories from the local cache.
Uses GitPython for git operations and integrates with SQLModel database.
"""

import re
import shutil
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from git import FetchInfo, GitCommandError, InvalidGitRepositoryError, Repo
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .database import DatabaseConfig, get_session
from .models import Repository


class GitRepository:
    """
    Git repository management class for KodeKlip.

    Handles cloning, updating, and managing git repositories in the local cache.
    Integrates with the database to track repository metadata and status.
    """

    def __init__(self, db_path: str | None = None):
        """
        Initialize GitRepository manager.

        Args:
            db_path: Optional custom database path
        """
        self.config = DatabaseConfig(db_path)
        self.console = Console()

        # Ensure repos directory exists
        self.repos_dir = self.config.kodeklip_dir / "repos"
        self.repos_dir.mkdir(parents=True, exist_ok=True)

    def validate_repository_url(self, url: str) -> bool:
        """
        Validate if URL is a supported git repository URL.

        Supports GitHub, GitLab, Bitbucket, and generic git URLs.

        Args:
            url: Repository URL to validate

        Returns:
            True if URL is valid, False otherwise
        """
        if not url or not isinstance(url, str):
            return False

        # Common git URL patterns
        patterns = [
            # GitHub patterns
            r"^https://github\.com/[\w\-\.]+/[\w\-\.]+(?:\.git)?/?$",
            r"^git@github\.com:[\w\-\.]+/[\w\-\.]+(?:\.git)?$",
            # GitLab patterns
            r"^https://gitlab\.com/[\w\-\.]+/[\w\-\.]+(?:\.git)?/?$",
            r"^git@gitlab\.com:[\w\-\.]+/[\w\-\.]+(?:\.git)?$",
            # Bitbucket patterns
            r"^https://bitbucket\.org/[\w\-\.]+/[\w\-\.]+(?:\.git)?/?$",
            r"^git@bitbucket\.org:[\w\-\.]+/[\w\-\.]+(?:\.git)?$",
            # Generic git patterns
            r"^https?://[^/]+/.*\.git/?$",
            r"^git@[^:]+:.*\.git$",
            r"^ssh://git@[^/]+/.*\.git$",
        ]

        return any(re.match(pattern, url.strip()) for pattern in patterns)

    def _get_local_path(self, alias: str) -> Path:
        """
        Get local filesystem path for repository alias.

        Args:
            alias: Repository alias

        Returns:
            Path object for repository location
        """
        return self.repos_dir / alias

    def clone_repository(
        self, url: str, alias: str, progress_callback: Callable | None = None
    ) -> tuple[bool, str, Repository | None]:
        """
        Clone repository to local cache.

        Args:
            url: Git repository URL
            alias: Unique alias for the repository
            progress_callback: Optional callback for progress updates

        Returns:
            Tuple of (success, message, repository_record)
        """
        # Validate inputs
        if not self.validate_repository_url(url):
            return False, f"Invalid repository URL: {url}", None

        if not alias or not isinstance(alias, str) or len(alias.strip()) == 0:
            return False, "Repository alias cannot be empty", None

        alias = alias.strip()
        local_path = self._get_local_path(alias)

        # Check if repository already exists locally
        if local_path.exists():
            return False, f"Repository with alias '{alias}' already exists", None

        # Check if alias already exists in database
        with get_session(str(self.config.db_path)) as session:
            from sqlmodel import select

            existing_repo = session.exec(
                select(Repository).where(Repository.alias == alias)
            ).first()
            if existing_repo:
                return (
                    False,
                    f"Repository alias '{alias}' already exists in database",
                    None,
                )

        try:
            # Clone repository with progress
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console,
                transient=True,
            ) as progress:
                task = progress.add_task(f"Cloning {alias}...", total=None)

                # Clone the repository
                _ = Repo.clone_from(url, local_path, progress=progress_callback)

                progress.update(task, description=f"Cloned {alias} successfully")

            # Verify clone was successful
            if not local_path.exists() or not (local_path / ".git").exists():
                return (
                    False,
                    "Clone appeared to succeed but repository not found locally",
                    None,
                )

            # Create database record
            with get_session(str(self.config.db_path)) as session:
                db_repo = Repository(
                    alias=alias, url=url, local_path=str(local_path), indexed=False
                )
                session.add(db_repo)
                session.commit()
                session.refresh(db_repo)

                return True, f"Successfully cloned {alias} to {local_path}", db_repo

        except GitCommandError as e:
            # Clean up partial clone if it exists
            if local_path.exists():
                shutil.rmtree(local_path, ignore_errors=True)

            error_msg = f"Git clone failed: {str(e)}"
            if "Authentication failed" in str(e):
                error_msg += "\nNote: For private repositories, ensure your SSH keys are configured or use a personal access token."
            elif "Repository not found" in str(e):
                error_msg += "\nThe repository URL may be incorrect or the repository may not exist."
            elif "Network is unreachable" in str(e) or "Temporary failure" in str(e):
                error_msg += "\nNetwork error. Please check your internet connection and try again."

            return False, error_msg, None

        except Exception as e:
            # Clean up partial clone if it exists
            if local_path.exists():
                shutil.rmtree(local_path, ignore_errors=True)

            return False, f"Unexpected error during clone: {str(e)}", None

    def repository_exists(self, alias: str) -> bool:
        """
        Check if repository exists both locally and in database.

        Args:
            alias: Repository alias to check

        Returns:
            True if repository exists, False otherwise
        """
        local_path = self._get_local_path(alias)

        # Check local filesystem
        if not local_path.exists() or not (local_path / ".git").exists():
            return False

        # Check database
        with get_session(str(self.config.db_path)) as session:
            from sqlmodel import select

            repo = session.exec(
                select(Repository).where(Repository.alias == alias)
            ).first()
            return repo is not None

    def get_repository_info(self, alias: str) -> Repository | None:
        """
        Get repository information from database.

        Args:
            alias: Repository alias

        Returns:
            Repository record or None if not found
        """
        with get_session(str(self.config.db_path)) as session:
            from sqlmodel import select

            return session.exec(
                select(Repository).where(Repository.alias == alias)
            ).first()

    def list_repositories(self) -> list[Repository]:
        """
        List all repositories in the database.

        Returns:
            List of Repository records
        """
        with get_session(str(self.config.db_path)) as session:
            from sqlmodel import select

            return list(session.exec(select(Repository)).all())

    def update_repository(
        self, alias: str, progress_callback: Callable | None = None  # noqa: ARG002
    ) -> tuple[bool, str, bool]:
        """
        Update repository by pulling latest changes.

        Args:
            alias: Repository alias to update
            progress_callback: Optional callback for progress updates

        Returns:
            Tuple of (success, message, has_changes)
        """
        if not self.repository_exists(alias):
            return False, f"Repository '{alias}' does not exist", False

        local_path = self._get_local_path(alias)

        try:
            # Open existing repository
            repo = Repo(local_path)

            # Check if repository is in a valid state
            if repo.is_dirty(untracked_files=True):
                return False, f"Repository '{alias}' has uncommitted changes", False

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console,
                transient=True,
            ) as progress:
                task = progress.add_task(f"Updating {alias}...", total=None)

                # Fetch changes from remote
                fetch_info = repo.remotes.origin.fetch()

                # Check if there are new commits
                has_changes = False
                for info in fetch_info:
                    # FetchInfo flags: Check if not up to date
                    if info.flags != FetchInfo.HEAD_UPTODATE:
                        has_changes = True
                        break

                if has_changes:
                    # Pull changes
                    _ = repo.remotes.origin.pull()
                    progress.update(
                        task, description=f"Updated {alias} with new changes"
                    )
                    message = f"Successfully updated {alias} - pulled new changes"
                else:
                    progress.update(task, description=f"{alias} is already up to date")
                    message = f"Repository {alias} is already up to date"

            # Update database record with timestamp
            with get_session(str(self.config.db_path)) as session:
                from sqlmodel import select

                repo_record = session.exec(
                    select(Repository).where(Repository.alias == alias)
                ).first()
                if repo_record:
                    repo_record.last_updated = datetime.utcnow()
                    session.add(repo_record)
                    session.commit()

            return True, message, has_changes

        except GitCommandError as e:
            error_msg = f"Git update failed: {str(e)}"
            if "Authentication failed" in str(e):
                error_msg += "\nNote: For private repositories, ensure your SSH keys are configured or use a personal access token."
            elif "Network is unreachable" in str(e) or "Temporary failure" in str(e):
                error_msg += "\nNetwork error. Please check your internet connection and try again."

            return False, error_msg, False

        except InvalidGitRepositoryError:
            return (
                False,
                f"Local repository '{alias}' is corrupted or not a valid git repository",
                False,
            )

        except Exception as e:
            return False, f"Unexpected error during update: {str(e)}", False

    def check_remote_updates(self, alias: str) -> tuple[bool, str, bool]:
        """
        Check if remote repository has updates without pulling.

        Args:
            alias: Repository alias to check

        Returns:
            Tuple of (success, message, has_updates)
        """
        if not self.repository_exists(alias):
            return False, f"Repository '{alias}' does not exist", False

        local_path = self._get_local_path(alias)

        try:
            repo = Repo(local_path)

            # Fetch latest refs from remote (without dry_run to avoid issues)
            fetch_info = repo.remotes.origin.fetch()

            # Check if there would be changes
            has_updates = False
            for info in fetch_info:
                if info.flags != FetchInfo.HEAD_UPTODATE:
                    has_updates = True
                    break

            if has_updates:
                message = f"Repository {alias} has remote updates available"
            else:
                message = f"Repository {alias} is up to date with remote"

            return True, message, has_updates

        except GitCommandError as e:
            error_msg = f"Failed to check remote updates: {str(e)}"
            if "Network is unreachable" in str(e) or "Temporary failure" in str(e):
                error_msg += "\nNetwork error. Please check your internet connection and try again."

            return False, error_msg, False

        except InvalidGitRepositoryError:
            return (
                False,
                f"Local repository '{alias}' is corrupted or not a valid git repository",
                False,
            )

        except Exception as e:
            return False, f"Unexpected error checking remote updates: {str(e)}", False

    def get_repository_status(self, alias: str) -> tuple[bool, str, dict]:
        """
        Get detailed status information about a repository.

        Args:
            alias: Repository alias

        Returns:
            Tuple of (success, message, status_dict)
        """
        if not self.repository_exists(alias):
            return False, f"Repository '{alias}' does not exist", {}

        local_path = self._get_local_path(alias)
        status = {}

        try:
            repo = Repo(local_path)

            # Basic repository info
            status.update(
                {
                    "alias": alias,
                    "local_path": str(local_path),
                    "exists": True,
                    "is_git_repo": True,
                    "current_branch": repo.active_branch.name,
                    "total_commits": len(list(repo.iter_commits())),
                    "is_dirty": repo.is_dirty(untracked_files=True),
                    "untracked_files": len(repo.untracked_files),
                    "has_remote": len(repo.remotes) > 0,
                }
            )

            # Remote information
            if repo.remotes:
                origin = repo.remotes.origin
                status.update(
                    {
                        "remote_url": list(origin.urls)[0],
                        "remote_refs": len(list(origin.refs)),
                    }
                )

            # Get database info
            with get_session(str(self.config.db_path)) as session:
                from sqlmodel import select

                repo_record = session.exec(
                    select(Repository).where(Repository.alias == alias)
                ).first()
                if repo_record:
                    status.update(
                        {
                            "last_updated": repo_record.last_updated,
                            "indexed": repo_record.indexed,
                            "database_url": repo_record.url,
                        }
                    )

            return True, f"Status retrieved for {alias}", status

        except InvalidGitRepositoryError:
            status.update(
                {
                    "alias": alias,
                    "local_path": str(local_path),
                    "exists": local_path.exists(),
                    "is_git_repo": False,
                    "error": "Not a valid git repository",
                }
            )
            return False, f"Repository '{alias}' is not a valid git repository", status

        except Exception as e:
            return False, f"Error getting status for {alias}: {str(e)}", status

    def remove_repository(
        self, alias: str, keep_files: bool = False
    ) -> tuple[bool, str]:
        """
        Remove repository from local cache and database.

        Args:
            alias: Repository alias to remove
            keep_files: If True, keep local files but remove from database

        Returns:
            Tuple of (success, message)
        """
        # Check if repository exists in database
        with get_session(str(self.config.db_path)) as session:
            from sqlmodel import select

            repo_record = session.exec(
                select(Repository).where(Repository.alias == alias)
            ).first()

            if not repo_record:
                return False, f"Repository '{alias}' not found in database"

            local_path = self._get_local_path(alias)

            try:
                # Remove from database first
                session.delete(repo_record)
                session.commit()

                # Remove local files if requested
                if not keep_files and local_path.exists():
                    shutil.rmtree(local_path, ignore_errors=True)

                    # Verify removal
                    if local_path.exists():
                        return (
                            False,
                            f"Failed to completely remove local files for '{alias}'",
                        )

                    message = (
                        f"Successfully removed repository '{alias}' and local files"
                    )
                else:
                    if keep_files:
                        message = f"Removed repository '{alias}' from database (kept local files)"
                    else:
                        message = f"Removed repository '{alias}' from database (no local files found)"

                return True, message

            except Exception as e:
                # Rollback database changes if file removal fails
                session.rollback()
                return False, f"Failed to remove repository '{alias}': {str(e)}"

    def cleanup_orphaned_files(self) -> tuple[bool, str, dict]:
        """
        Clean up local repository directories that don't exist in database.

        Returns:
            Tuple of (success, message, cleanup_info)
        """
        cleanup_info: dict[str, Any] = {
            "orphaned_dirs": [],
            "removed_dirs": [],
            "failed_removals": [],
            "space_freed_mb": 0.0,
        }

        try:
            # Get all aliases from database
            with get_session(str(self.config.db_path)) as session:
                from sqlmodel import select

                db_aliases = {
                    repo.alias for repo in session.exec(select(Repository)).all()
                }

            # Check local repository directories
            if not self.repos_dir.exists():
                return True, "No repositories directory found", cleanup_info

            for local_dir in self.repos_dir.iterdir():
                if local_dir.is_dir() and local_dir.name not in db_aliases:
                    cleanup_info["orphaned_dirs"].append(local_dir.name)

                    try:
                        # Calculate directory size before removal
                        total_size = sum(
                            f.stat().st_size
                            for f in local_dir.rglob("*")
                            if f.is_file()
                        )
                        size_mb = total_size / (1024 * 1024)

                        # Remove directory
                        shutil.rmtree(local_dir)

                        cleanup_info["removed_dirs"].append(local_dir.name)
                        cleanup_info["space_freed_mb"] += size_mb

                    except Exception as e:
                        cleanup_info["failed_removals"].append(
                            {"directory": local_dir.name, "error": str(e)}
                        )

            if cleanup_info["orphaned_dirs"]:
                message = f"Cleaned up {len(cleanup_info['removed_dirs'])} orphaned directories, freed {cleanup_info['space_freed_mb']:.2f} MB"
                if cleanup_info["failed_removals"]:
                    message += f" ({len(cleanup_info['failed_removals'])} failed)"
            else:
                message = "No orphaned directories found"

            return True, message, cleanup_info

        except Exception as e:
            return False, f"Cleanup failed: {str(e)}", cleanup_info

    def sync_database_with_filesystem(self) -> tuple[bool, str, dict]:
        """
        Synchronize database records with actual filesystem state.

        Returns:
            Tuple of (success, message, sync_info)
        """
        sync_info: dict[str, list[str]] = {
            "missing_repos": [],
            "invalid_repos": [],
            "updated_repos": [],
            "removed_records": [],
        }

        try:
            with get_session(str(self.config.db_path)) as session:
                from sqlmodel import select

                repositories = list(session.exec(select(Repository)).all())

                for repo in repositories:
                    local_path = Path(repo.local_path)

                    # Check if local repository exists
                    if not local_path.exists():
                        sync_info["missing_repos"].append(repo.alias)
                        # Remove from database
                        session.delete(repo)
                        sync_info["removed_records"].append(repo.alias)
                        continue

                    # Check if it's a valid git repository
                    if not (local_path / ".git").exists():
                        sync_info["invalid_repos"].append(repo.alias)
                        # Remove from database
                        session.delete(repo)
                        sync_info["removed_records"].append(repo.alias)
                        continue

                    # Check if local path matches expected path
                    expected_path = self._get_local_path(repo.alias)
                    if local_path != expected_path:
                        sync_info["updated_repos"].append(repo.alias)
                        # Update database record
                        repo.local_path = str(expected_path)
                        session.add(repo)

                session.commit()

            total_issues = (
                len(sync_info["missing_repos"])
                + len(sync_info["invalid_repos"])
                + len(sync_info["updated_repos"])
            )

            if total_issues > 0:
                message = f"Synchronized database: removed {len(sync_info['removed_records'])} records, updated {len(sync_info['updated_repos'])} paths"
            else:
                message = "Database is already synchronized with filesystem"

            return True, message, sync_info

        except Exception as e:
            return False, f"Database synchronization failed: {str(e)}", sync_info

    def get_disk_usage(self) -> tuple[bool, str, dict]:
        """
        Calculate disk usage for all repositories.

        Returns:
            Tuple of (success, message, usage_info)
        """
        usage_info: dict[str, Any] = {
            "total_repos": 0,
            "total_size_mb": 0.0,
            "repo_sizes": {},
            "largest_repos": [],
            "avg_size_mb": 0.0,
        }

        try:
            with get_session(str(self.config.db_path)) as session:
                from sqlmodel import select

                repositories = list(session.exec(select(Repository)).all())

            usage_info["total_repos"] = len(repositories)

            for repo in repositories:
                local_path = Path(repo.local_path)

                if local_path.exists():
                    try:
                        # Calculate directory size
                        total_size = sum(
                            f.stat().st_size
                            for f in local_path.rglob("*")
                            if f.is_file()
                        )
                        size_mb = total_size / (1024 * 1024)

                        usage_info["repo_sizes"][repo.alias] = size_mb
                        usage_info["total_size_mb"] += size_mb

                    except Exception:
                        # Handle permission errors, etc.
                        usage_info["repo_sizes"][repo.alias] = 0.0

            # Calculate average size
            if usage_info["total_repos"] > 0:
                usage_info["avg_size_mb"] = (
                    usage_info["total_size_mb"] / usage_info["total_repos"]
                )

            # Find largest repositories
            sorted_repos = sorted(
                usage_info["repo_sizes"].items(), key=lambda x: x[1], reverse=True
            )
            usage_info["largest_repos"] = sorted_repos[:5]  # Top 5

            message = f"Total disk usage: {usage_info['total_size_mb']:.2f} MB across {usage_info['total_repos']} repositories"

            return True, message, usage_info

        except Exception as e:
            return False, f"Failed to calculate disk usage: {str(e)}", usage_info
