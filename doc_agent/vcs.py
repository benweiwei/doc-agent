"""Version control system integration using GitPython."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml
from git import GitCommandError, InvalidGitRepositoryError, NoSuchPathError, Repo

logger = logging.getLogger(__name__)

DOCUMENT_EXTENSIONS = {".md", ".txt", ".rst"}
BRANCH_PREFIX = "target/"
BRANCHES_META_DIR = ".doc-agent"
BRANCHES_META_FILE = "branches.yaml"


class VCSError(Exception):
    """Base exception for version control operations."""


class BranchNotFoundError(VCSError):
    """Raised when a branch does not exist."""


class DocumentNotFoundError(VCSError):
    """Raised when a document does not exist."""


class MergeConflictError(VCSError):
    """Raised when a merge results in conflicts."""


class VersionControl:
    """Git repository wrapper for documentation workflows.

    Encapsulates all Git operations needed by the doc-agent system,
    including branch management, document CRUD, and diff/history.
    """

    def __init__(self, workspace_path: Path) -> None:
        """Initialize with workspace path.

        Args:
            workspace_path: Path to the Git repository root.
        """
        self.workspace_path = Path(workspace_path).resolve()
        self._repo: Optional[Repo] = None

    @property
    def repo(self) -> Repo:
        """Lazy-load the Repo object."""
        if self._repo is None:
            try:
                self._repo = Repo(self.workspace_path)
            except (InvalidGitRepositoryError, NoSuchPathError) as e:
                raise VCSError(
                    f"Not a valid Git repository: {self.workspace_path}"
                ) from e
        return self._repo

    def init_workspace(self) -> None:
        """Initialize Git repository if not exists, create main branch.

        If the repository already exists, this is a no-op.
        Creates an initial commit on 'main' branch if the repo is brand new.
        """
        self.workspace_path.mkdir(parents=True, exist_ok=True)

        try:
            self._repo = Repo(self.workspace_path)
            logger.info("Repository already exists at %s", self.workspace_path)
        except (InvalidGitRepositoryError, NoSuchPathError):
            self._repo = Repo.init(self.workspace_path)
            logger.info("Initialized new repository at %s", self.workspace_path)

        # Ensure we have a main branch with at least one commit
        if not self._repo.heads:
            # Create initial commit so 'main' branch exists
            meta_dir = self.workspace_path / BRANCHES_META_DIR
            meta_dir.mkdir(parents=True, exist_ok=True)
            meta_file = meta_dir / BRANCHES_META_FILE
            meta_file.write_text(yaml.dump({"branches": {}}, default_flow_style=False))
            self._repo.index.add([str(Path(BRANCHES_META_DIR) / BRANCHES_META_FILE)])
            self._repo.index.commit("Initial commit: initialize doc-agent workspace")
            # Rename default branch to main
            if self._repo.active_branch.name != "main":
                self._repo.active_branch.rename("main")
        elif "main" not in [h.name for h in self._repo.heads]:
            # Repo has commits but no 'main' branch - create one
            self._repo.create_head("main")

    def list_documents(self, branch: str = None) -> list[str]:
        """List all document files on the given branch.

        Args:
            branch: Branch name to list documents from. Defaults to current branch.

        Returns:
            List of document file paths (relative to repo root).
        """
        branch = branch or self.get_current_branch()
        try:
            commit = self.repo.commit(branch)
        except Exception as e:
            raise BranchNotFoundError(f"Branch '{branch}' not found") from e

        documents = []
        for blob in commit.tree.traverse():
            if hasattr(blob, "path"):
                path = Path(blob.path)
                if path.suffix.lower() in DOCUMENT_EXTENSIONS:
                    documents.append(blob.path)
        return sorted(documents)

    def load_document(self, doc_id: str, branch: str = None) -> tuple[str, str]:
        """Load document content without changing the current branch.

        Uses `git show branch:path` internally to read file content.

        Args:
            doc_id: Document file path relative to repo root.
            branch: Branch to read from. Defaults to current branch.

        Returns:
            Tuple of (content, branch_name).

        Raises:
            DocumentNotFoundError: If the document does not exist on the branch.
        """
        branch = branch or self.get_current_branch()
        try:
            content = self.repo.git.show(f"{branch}:{doc_id}")
        except GitCommandError as e:
            raise DocumentNotFoundError(
                f"Document '{doc_id}' not found on branch '{branch}'"
            ) from e
        return content, branch

    def save_document(
        self,
        doc_id: str,
        content: str,
        message: str = None,
        branch: str = None,
    ) -> str:
        """Save document content and commit.

        If the target branch differs from the current branch, handles
        stash/switch/write/commit/switch-back automatically.

        Args:
            doc_id: Document file path relative to repo root.
            content: Document content to write.
            message: Commit message. Auto-generated if not provided.
            branch: Target branch. Defaults to current branch.

        Returns:
            The commit hash string.
        """
        branch = branch or self.get_current_branch()
        message = message or f"Update {doc_id}"
        current_branch = self.get_current_branch()
        need_switch = branch != current_branch

        stashed = False
        try:
            if need_switch:
                # Stash any uncommitted changes on current branch
                if self.repo.is_dirty(untracked_files=True):
                    self.repo.git.stash("save", "--include-untracked",
                                        "doc-agent: auto-stash before branch switch")
                    stashed = True
                self.repo.git.checkout(branch)

            # Write the document file
            file_path = self.workspace_path / doc_id
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

            # Stage and commit
            self.repo.index.add([doc_id])
            commit = self.repo.index.commit(message)
            commit_hash = commit.hexsha

        except GitCommandError as e:
            raise VCSError(f"Failed to save document '{doc_id}': {e}") from e
        finally:
            if need_switch:
                try:
                    self.repo.git.checkout(current_branch)
                except GitCommandError:
                    logger.error("Failed to switch back to branch '%s'", current_branch)
                if stashed:
                    try:
                        self.repo.git.stash("pop")
                    except GitCommandError:
                        logger.warning("Failed to pop stash, changes remain in stash")

        return commit_hash

    def create_branch(
        self,
        branch_name: str,
        delivery_target: str = "",
        base_branch: str = "main",
    ) -> None:
        """Create a new document branch with target/ prefix.

        Args:
            branch_name: The branch name (without prefix).
            delivery_target: Description of the delivery target.
            base_branch: Branch to base the new branch on.

        Raises:
            VCSError: If branch already exists or base branch not found.
        """
        full_branch_name = f"{BRANCH_PREFIX}{branch_name}"

        # Check if branch already exists
        if full_branch_name in [h.name for h in self.repo.heads]:
            raise VCSError(f"Branch '{full_branch_name}' already exists")

        # Verify base branch exists
        if base_branch not in [h.name for h in self.repo.heads]:
            raise BranchNotFoundError(f"Base branch '{base_branch}' not found")

        try:
            # Create branch from base
            base_ref = self.repo.heads[base_branch]
            new_branch = self.repo.create_head(full_branch_name, base_ref.commit)

            # Store delivery_target metadata
            if delivery_target:
                self._update_branch_metadata(
                    full_branch_name, delivery_target, new_branch
                )

            logger.info("Created branch '%s' from '%s'", full_branch_name, base_branch)
        except GitCommandError as e:
            raise VCSError(f"Failed to create branch '{full_branch_name}': {e}") from e

    def _update_branch_metadata(
        self, branch_name: str, delivery_target: str, branch_head
    ) -> None:
        """Write delivery_target info to .doc-agent/branches.yaml on the branch."""
        current_branch = self.get_current_branch()
        stashed = False

        try:
            if self.repo.is_dirty(untracked_files=True):
                self.repo.git.stash("save", "--include-untracked",
                                    "doc-agent: auto-stash for metadata update")
                stashed = True

            self.repo.git.checkout(branch_name)

            # Read or create metadata file
            meta_dir = self.workspace_path / BRANCHES_META_DIR
            meta_dir.mkdir(parents=True, exist_ok=True)
            meta_file = meta_dir / BRANCHES_META_FILE

            if meta_file.exists():
                data = yaml.safe_load(meta_file.read_text()) or {}
            else:
                data = {}

            if "branches" not in data:
                data["branches"] = {}

            data["branches"][branch_name] = {
                "delivery_target": delivery_target,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

            meta_file.write_text(yaml.dump(data, default_flow_style=False))
            self.repo.index.add([str(Path(BRANCHES_META_DIR) / BRANCHES_META_FILE)])
            self.repo.index.commit(
                f"doc-agent: set delivery target for {branch_name}"
            )
        finally:
            self.repo.git.checkout(current_branch)
            if stashed:
                try:
                    self.repo.git.stash("pop")
                except GitCommandError:
                    logger.warning("Failed to pop stash after metadata update")

    def _load_branch_metadata(self) -> dict:
        """Load branch metadata from .doc-agent/branches.yaml on current branch."""
        meta_file = self.workspace_path / BRANCHES_META_DIR / BRANCHES_META_FILE
        if not meta_file.exists():
            # Try to read from main branch via git show
            try:
                content = self.repo.git.show(
                    f"main:{BRANCHES_META_DIR}/{BRANCHES_META_FILE}"
                )
                return yaml.safe_load(content) or {}
            except GitCommandError:
                return {}
        data = yaml.safe_load(meta_file.read_text())
        return data or {}

    def list_branches(self) -> list[dict]:
        """List all branches with metadata.

        Returns:
            List of dicts with keys: name, delivery_target, head_commit, is_current.
        """
        current = self.get_current_branch()

        # Collect metadata from all branches
        metadata = self._collect_all_branch_metadata()

        branches = []
        for head in self.repo.heads:
            branch_meta = metadata.get(head.name, {})
            branches.append({
                "name": head.name,
                "delivery_target": branch_meta.get("delivery_target", ""),
                "head_commit": head.commit.hexsha[:8],
                "is_current": head.name == current,
            })
        return branches

    def _collect_all_branch_metadata(self) -> dict:
        """Collect branch metadata across all branches."""
        all_metadata: dict = {}
        for head in self.repo.heads:
            try:
                content = self.repo.git.show(
                    f"{head.name}:{BRANCHES_META_DIR}/{BRANCHES_META_FILE}"
                )
                data = yaml.safe_load(content) or {}
                branch_entries = data.get("branches", {})
                all_metadata.update(branch_entries)
            except GitCommandError:
                continue
        return all_metadata

    def rename_branch(self, old_name: str, new_name: str) -> None:
        """Rename a branch and update branches.yaml metadata.

        Args:
            old_name: Current branch name.
            new_name: New branch name.

        Raises:
            BranchNotFoundError: If old_name does not exist.
            VCSError: If new_name already exists or rename fails.
        """
        branch_names = [h.name for h in self.repo.heads]
        if old_name not in branch_names:
            raise BranchNotFoundError(f"Branch '{old_name}' not found")
        if new_name in branch_names:
            raise VCSError(f"Branch '{new_name}' already exists")

        try:
            self.repo.git.branch("-m", old_name, new_name)
        except GitCommandError as e:
            raise VCSError(f"Failed to rename branch '{old_name}' to '{new_name}': {e}") from e

        # Update metadata in branches.yaml
        self._rename_branch_metadata(old_name, new_name)
        logger.info("Renamed branch '%s' to '%s'", old_name, new_name)

    def _rename_branch_metadata(self, old_name: str, new_name: str) -> None:
        """Update branch name in .doc-agent/branches.yaml on the renamed branch."""
        current_branch = self.get_current_branch()
        stashed = False

        try:
            if self.repo.is_dirty(untracked_files=True):
                self.repo.git.stash("save", "--include-untracked",
                                    "doc-agent: auto-stash for branch rename metadata")
                stashed = True

            self.repo.git.checkout(new_name)

            meta_dir = self.workspace_path / BRANCHES_META_DIR
            meta_dir.mkdir(parents=True, exist_ok=True)
            meta_file = meta_dir / BRANCHES_META_FILE

            if meta_file.exists():
                data = yaml.safe_load(meta_file.read_text()) or {}
            else:
                data = {}

            branches = data.get("branches", {})
            if old_name in branches:
                branches[new_name] = branches.pop(old_name)
                data["branches"] = branches
                meta_file.write_text(yaml.dump(data, default_flow_style=False))
                self.repo.index.add([str(Path(BRANCHES_META_DIR) / BRANCHES_META_FILE)])
                self.repo.index.commit(
                    f"doc-agent: rename branch metadata {old_name} -> {new_name}"
                )
        except GitCommandError as e:
            logger.warning("Failed to update branch metadata during rename: %s", e)
        finally:
            try:
                self.repo.git.checkout(current_branch if current_branch != old_name else new_name)
            except GitCommandError:
                logger.error("Failed to switch back after rename metadata update")
            if stashed:
                try:
                    self.repo.git.stash("pop")
                except GitCommandError:
                    logger.warning("Failed to pop stash after rename metadata update")

    def switch_branch(self, branch_name: str) -> None:
        """Switch to the specified branch.

        Args:
            branch_name: Name of the branch to switch to.

        Raises:
            BranchNotFoundError: If the branch does not exist.
        """
        if branch_name not in [h.name for h in self.repo.heads]:
            raise BranchNotFoundError(f"Branch '{branch_name}' not found")
        try:
            self.repo.git.checkout(branch_name)
        except GitCommandError as e:
            raise VCSError(f"Failed to switch to branch '{branch_name}': {e}") from e

    def merge_branches(self, source_branch: str, target_branch: str) -> dict:
        """Merge source branch into target branch.

        Args:
            source_branch: Branch to merge from.
            target_branch: Branch to merge into.

        Returns:
            Dict with keys: success (bool), conflicts (list), merge_commit (str).
        """
        # Validate branches exist
        branch_names = [h.name for h in self.repo.heads]
        if source_branch not in branch_names:
            raise BranchNotFoundError(f"Source branch '{source_branch}' not found")
        if target_branch not in branch_names:
            raise BranchNotFoundError(f"Target branch '{target_branch}' not found")

        current_branch = self.get_current_branch()
        stashed = False

        try:
            # Stash if dirty
            if self.repo.is_dirty(untracked_files=True):
                self.repo.git.stash("save", "--include-untracked",
                                    "doc-agent: auto-stash before merge")
                stashed = True

            # Switch to target branch
            self.repo.git.checkout(target_branch)

            # Attempt merge
            try:
                self.repo.git.merge(source_branch)
                merge_commit = self.repo.head.commit.hexsha
                return {
                    "success": True,
                    "conflicts": [],
                    "merge_commit": merge_commit,
                }
            except GitCommandError:
                # Check for conflicts
                conflicts = self._get_conflict_files()
                if conflicts:
                    # Abort the merge to leave repo in clean state
                    self.repo.git.merge("--abort")
                    return {
                        "success": False,
                        "conflicts": conflicts,
                        "merge_commit": "",
                    }
                raise

        except (BranchNotFoundError, MergeConflictError):
            raise
        except GitCommandError as e:
            raise VCSError(f"Merge failed: {e}") from e
        finally:
            # Switch back to original branch
            try:
                self.repo.git.checkout(current_branch)
            except GitCommandError:
                logger.error("Failed to switch back to '%s' after merge", current_branch)
            if stashed:
                try:
                    self.repo.git.stash("pop")
                except GitCommandError:
                    logger.warning("Failed to pop stash after merge")

    def _get_conflict_files(self) -> list[str]:
        """Get list of files with merge conflicts."""
        conflicts = []
        try:
            status_output = self.repo.git.status("--porcelain")
            for line in status_output.splitlines():
                if line.startswith("UU") or line.startswith("AA") or line.startswith("DU") or line.startswith("UD"):
                    # Conflicted files
                    conflicts.append(line[3:].strip())
        except GitCommandError:
            pass
        return conflicts

    def get_conflict_details(
        self, doc_id: str, source_branch: str, target_branch: str
    ) -> dict:
        """Get conflict details showing base/ours/theirs content for a document.

        Performs a merge without committing to extract three-way content,
        then aborts the merge to restore clean state.

        Args:
            doc_id: Document file path relative to repo root.
            source_branch: Branch being merged in (theirs).
            target_branch: Branch being merged into (ours).

        Returns:
            Dict with keys: doc_id, base, ours, theirs, has_conflict.

        Raises:
            BranchNotFoundError: If branches don't exist.
            DocumentNotFoundError: If document doesn't exist on either branch.
        """
        branch_names = [h.name for h in self.repo.heads]
        if source_branch not in branch_names:
            raise BranchNotFoundError(f"Source branch '{source_branch}' not found")
        if target_branch not in branch_names:
            raise BranchNotFoundError(f"Target branch '{target_branch}' not found")

        current_branch = self.get_current_branch()
        stashed = False

        try:
            # Stash if dirty
            if self.repo.is_dirty(untracked_files=True):
                self.repo.git.stash(
                    "save", "--include-untracked",
                    "doc-agent: auto-stash before conflict details",
                )
                stashed = True

            # Switch to target branch (ours)
            self.repo.git.checkout(target_branch)

            # Get ours content
            try:
                ours_content = self.repo.git.show(f"{target_branch}:{doc_id}")
            except GitCommandError:
                ours_content = ""

            # Get theirs content
            try:
                theirs_content = self.repo.git.show(f"{source_branch}:{doc_id}")
            except GitCommandError:
                theirs_content = ""

            # Find merge base
            try:
                merge_base = self.repo.git.merge_base(target_branch, source_branch).strip()
                try:
                    base_content = self.repo.git.show(f"{merge_base}:{doc_id}")
                except GitCommandError:
                    base_content = ""
            except GitCommandError:
                base_content = ""

            has_conflict = ours_content != theirs_content

            return {
                "doc_id": doc_id,
                "base": base_content,
                "ours": ours_content,
                "theirs": theirs_content,
                "has_conflict": has_conflict,
                "source_branch": source_branch,
                "target_branch": target_branch,
            }

        except (BranchNotFoundError, DocumentNotFoundError):
            raise
        except GitCommandError as e:
            raise VCSError(f"Failed to get conflict details for '{doc_id}': {e}") from e
        finally:
            try:
                self.repo.git.checkout(current_branch)
            except GitCommandError:
                logger.error(
                    "Failed to switch back to '%s' after conflict details",
                    current_branch,
                )
            if stashed:
                try:
                    self.repo.git.stash("pop")
                except GitCommandError:
                    logger.warning("Failed to pop stash after conflict details")

    def resolve_conflict(
        self,
        doc_id: str,
        resolution: str,
        source_branch: str,
        target_branch: str,
        message: Optional[str] = None,
    ) -> str:
        """Apply conflict resolution and commit the merge.

        Performs the merge, writes the resolved content, and commits.

        Args:
            doc_id: Document file path relative to repo root.
            resolution: The resolved content to write.
            source_branch: Branch being merged in.
            target_branch: Branch to merge into.
            message: Custom commit message. Auto-generated if not provided.

        Returns:
            The merge commit hash string.

        Raises:
            BranchNotFoundError: If branches don't exist.
            VCSError: If merge/commit fails.
        """
        branch_names = [h.name for h in self.repo.heads]
        if source_branch not in branch_names:
            raise BranchNotFoundError(f"Source branch '{source_branch}' not found")
        if target_branch not in branch_names:
            raise BranchNotFoundError(f"Target branch '{target_branch}' not found")

        current_branch = self.get_current_branch()
        stashed = False
        commit_message = message or (
            f"Merge '{source_branch}' into '{target_branch}': resolve {doc_id}"
        )

        try:
            # Stash if dirty
            if self.repo.is_dirty(untracked_files=True):
                self.repo.git.stash(
                    "save", "--include-untracked",
                    "doc-agent: auto-stash before conflict resolve",
                )
                stashed = True

            # Switch to target branch
            self.repo.git.checkout(target_branch)

            # Start the merge (will likely conflict)
            try:
                self.repo.git.merge(source_branch, "--no-commit")
            except GitCommandError:
                # Expected — conflicts cause non-zero exit
                pass

            # Write resolved content
            file_path = self.workspace_path / doc_id
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(resolution, encoding="utf-8")

            # Stage the resolved file and commit
            self.repo.index.add([doc_id])
            commit = self.repo.index.commit(commit_message)
            commit_hash = commit.hexsha

            logger.info(
                "Resolved conflict for '%s': merge '%s' into '%s' -> %s",
                doc_id, source_branch, target_branch, commit_hash[:8],
            )
            return commit_hash

        except (BranchNotFoundError,):
            raise
        except GitCommandError as e:
            # Abort merge on failure to leave clean state
            try:
                self.repo.git.merge("--abort")
            except GitCommandError:
                pass
            raise VCSError(
                f"Failed to resolve conflict for '{doc_id}': {e}"
            ) from e
        finally:
            try:
                self.repo.git.checkout(current_branch)
            except GitCommandError:
                logger.error(
                    "Failed to switch back to '%s' after conflict resolve",
                    current_branch,
                )
            if stashed:
                try:
                    self.repo.git.stash("pop")
                except GitCommandError:
                    logger.warning("Failed to pop stash after conflict resolve")

    def get_diff(
        self,
        doc_id: str,
        branch_a: str = None,
        branch_b: str = None,
        commit_a: str = None,
        commit_b: str = None,
    ) -> str:
        """Get diff for a document between branches or commits.

        Args:
            doc_id: Document file path relative to repo root.
            branch_a: First branch (or use commit_a).
            branch_b: Second branch (or use commit_b).
            commit_a: First commit hash (alternative to branch_a).
            commit_b: Second commit hash (alternative to branch_b).

        Returns:
            Unified diff string.
        """
        ref_a = commit_a or branch_a
        ref_b = commit_b or branch_b

        try:
            if ref_a and ref_b:
                return self.repo.git.diff(ref_a, ref_b, "--", doc_id)
            elif ref_a:
                # Diff between ref_a and working tree
                return self.repo.git.diff(ref_a, "--", doc_id)
            else:
                # Diff of unstaged changes
                return self.repo.git.diff("--", doc_id)
        except GitCommandError as e:
            raise VCSError(f"Failed to get diff for '{doc_id}': {e}") from e

    def get_history(
        self,
        doc_id: str = None,
        branch: str = None,
        limit: int = 50,
    ) -> list[dict]:
        """Get commit history.

        Args:
            doc_id: If provided, only show commits affecting this file.
            branch: Branch to show history for. Defaults to current.
            limit: Maximum number of entries to return.

        Returns:
            List of dicts with: commit_hash, message, author, timestamp.
        """
        branch = branch or self.get_current_branch()

        try:
            kwargs: dict = {"max_count": limit}
            if doc_id:
                kwargs["paths"] = doc_id

            commits = list(self.repo.iter_commits(branch, **kwargs))
        except GitCommandError as e:
            raise VCSError(f"Failed to get history: {e}") from e

        history = []
        for commit in commits:
            history.append({
                "commit_hash": commit.hexsha,
                "message": commit.message.strip(),
                "author": str(commit.author),
                "timestamp": datetime.fromtimestamp(
                    commit.committed_date, tz=timezone.utc
                ).isoformat(),
            })
        return history

    def get_current_branch(self) -> str:
        """Get the name of the current active branch.

        Returns:
            Branch name string.

        Raises:
            VCSError: If in detached HEAD state.
        """
        try:
            if self.repo.head.is_detached:
                return self.repo.head.commit.hexsha[:8]
            return self.repo.active_branch.name
        except (TypeError, ValueError) as e:
            raise VCSError(f"Cannot determine current branch: {e}") from e


    def get_all_documents(self) -> dict[str, list[str]]:
        """Scan all target/ branches, return {branch_name: [doc_ids]} mapping."""
        result = {}
        for head in self.repo.heads:
            if head.name.startswith(BRANCH_PREFIX) or head.name == "main":
                try:
                    result[head.name] = self.list_documents(head.name)
                except Exception:
                    result[head.name] = []
        return result

    def get_document_branches(self, doc_id: str) -> list[str]:
        """Return list of branch names that contain the specified document."""
        branches = []
        for head in self.repo.heads:
            if head.name.startswith(BRANCH_PREFIX) or head.name == "main":
                try:
                    docs = self.list_documents(head.name)
                    if doc_id in docs:
                        branches.append(head.name)
                except Exception:
                    continue
        return branches


# Backward compatibility alias
GitWorkspace = VersionControl
