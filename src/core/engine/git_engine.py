import os
import threading
from datetime import datetime
from typing import Dict, List, Optional

from git import Git, GitCommandError
from src.constants import GIT_AUTHOR_EMAIL, GIT_AUTHOR_NAME
from src.core.engine.base import SaveEngine, register_engine
from src.exceptions import BranchError, GitEngineError, SnapshotNotFoundError
from src.logger import LoggerFactory
from src.models.game import GameEntry
from src.models.snapshot_info import SnapshotInfo

logger = LoggerFactory.getLogger(__name__)

# %x1f = unit separator: collision-proof delimiter for log parsing
LOG_FORMAT = "%H%x1f%s%x1f%cI%x1f%an"


@register_engine("git")
class GitEngine(SaveEngine):
    """
    Git-based save engine.

    One git repository per game lives in the central vault. The repository
    is created bare and then reconfigured with core.worktree pointing at the
    live save folder, so the save folder itself stays completely clean.
    All commands run with explicit --git-dir/--work-tree flags, which makes
    behavior independent of cwd and of GitPython's worktree detection.
    """

    def __init__(self, game: GameEntry, repos_root: str):
        super().__init__(game=game, repos_root=repos_root)
        self.repo_path: str = os.path.join(
            os.fspath(repos_root), f"{game.slug}.git"
        )
        self.work_tree: str = os.fspath(game.path)
        self.branch: str = game.default_branch or "main"
        self._git = Git()
        # execute() passes argv straight to Popen - include
        # the binary ourselves.
        self._exe = (
            getattr(self._git, "GIT_PYTHON_GIT_EXECUTABLE", None) or "git"
        )
        # Reentrant: public methods take it and call other locked methods.
        self._lock = threading.RLock()

    # ---- plumbing -----------------------------------------------------------

    def _run(self, *args: str) -> str:
        """Run a git command bound to this repo dir + live worktree."""
        cmd = [
            self._exe,
            "--git-dir",
            self.repo_path,
            "--work-tree",
            self.work_tree,
            "-c",
            f"user.name={GIT_AUTHOR_NAME}",
            "-c",
            f"user.email={GIT_AUTHOR_EMAIL}",
            *args,
        ]
        return self._execute(cmd)

    def _run_repo_only(self, *args: str) -> str:
        """Run a git command that only touches the object database."""
        cmd = [
            self._exe,
            "--git-dir",
            self.repo_path,
            "-c",
            f"user.name={GIT_AUTHOR_NAME}",
            "-c",
            f"user.email={GIT_AUTHOR_EMAIL}",
            *args,
        ]
        return self._execute(cmd)

    def _execute(self, cmd: List[str]) -> str:
        try:
            return self._git.execute(cmd)  # type: ignore[return-value]
        except GitCommandError as ex:
            stderr = (getattr(ex, "stderr", "") or "").strip()
            raise GitEngineError(f"git {cmd[-1]} failed: {stderr}") from ex

    # ---- lifecycle ----------------------------------------------------------

    def init(self) -> None:
        with self._lock:
            head_file = os.path.join(self.repo_path, "HEAD")
            if not os.path.exists(head_file):
                os.makedirs(self.repo_path, exist_ok=True)
                self._run_repo_only(
                    "init", "--bare", "--quiet", self.repo_path
                )
                logger.info(f"Initialized vault repo at {self.repo_path}")

            # Un-bare the repo and bind it to the live folder.
            self._run_repo_only("config", "core.bare", "false")
            self._run_repo_only("config", "core.worktree", self.work_tree)
            # Binary saves must never be line-ending mangled.
            self._run_repo_only("config", "core.autocrlf", "false")
            # Auto-gc may grab the object db while the game is running.
            self._run_repo_only("config", "gc.auto", "0")

            if not self._head_is_valid():
                # Point unborn HEAD at the default branch.
                self._run_repo_only(
                    "symbolic-ref", "HEAD", f"refs/heads/{self.branch}"
                )

    def _head_is_valid(self) -> bool:
        try:
            out = self._run_repo_only(
                "rev-parse", "--verify", "--quiet", "HEAD"
            )
            return bool(out.strip())
        except GitEngineError:
            return False

    # ---- snapshots ----------------------------------------------------------

    def has_changes(self) -> bool:
        out = self._run("status", "--porcelain").strip()
        return bool(out)

    def snapshot(
        self, message: Optional[str] = None, allow_empty: bool = False
    ) -> Optional[SnapshotInfo]:
        message = (
            message
            or f"snapshot: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        with self._lock:
            self.init()
            self._run("add", "--all")
            dirty = self.has_changes()
            if not dirty and not allow_empty:
                logger.debug(f"[{self.game.name}] No changes to snapshot")
                return None
            extra = ["--allow-empty"] if not dirty else []
            self._run("commit", "--quiet", "-m", message, *extra)
            commit_id = self._run("rev-parse", "HEAD").strip()
            logger.info(
                f"[{self.game.name}] Snapshot {commit_id[:8]} "
                f"on '{self.current_branch()}'"
            )
            return self._get_snapshot(commit_id)

    def list_snapshots(
        self, branch: Optional[str] = None, limit: Optional[int] = None
    ) -> List[SnapshotInfo]:
        self.init()
        target = branch or self.current_branch()
        args = ["log", f"--format={LOG_FORMAT}", target]
        if limit:
            args.append(f"--max-count={limit}")
        try:
            out = self._run(*args)
        except GitEngineError as ex:
            if "unknown revision" in str(ex).lower():
                # Fresh repo without any commits yet: nothing to list.
                try:
                    self._run("rev-parse", "--verify", "--quiet", "HEAD")
                except GitEngineError:
                    return []
                raise BranchError(
                    f"No snapshots found for branch '{target}'"
                ) from ex
            raise
        kept = (ln for ln in out.splitlines() if ln.strip())
        return [self._parse_log_line(line) for line in kept]

    def restore(self, snapshot_id: str, hard: bool = False) -> SnapshotInfo:
        with self._lock:
            self.init()
            resolved = self._resolve_snapshot(snapshot_id)

            if self.has_changes():
                self.snapshot(
                    message="auto: pending changes before restore",
                    allow_empty=False,
                )

            if hard:
                self._run("reset", "--hard", resolved)
                logger.warning(
                    f"[{self.game.name}] Hard reset '{self.current_branch()}' "
                    f"to {resolved[:8]} - newer commits orphaned"
                )
                return self._get_snapshot(resolved)

            # Safe mode: make index+worktree match the old tree exactly
            # (read-tree removes files created after the snapshot), then
            # commit on top - history stays intact and reversible.
            self._run("read-tree", "--reset", "-u", resolved)
            self._run("commit", "--quiet", "-m", f"restore: to {resolved[:8]}")
            restored_id = self._run("rev-parse", "HEAD").strip()
            logger.info(
                f"[{self.game.name}] Restored state of {resolved[:8]} "
                f"as new snapshot {restored_id[:8]}"
            )
            return self._get_snapshot(restored_id)

    def _resolve_snapshot(self, snapshot_id: str) -> str:
        try:
            resolved = self._run_repo_only(
                "rev-parse", "--verify", "--quiet", f"{snapshot_id}^{{commit}}"
            ).strip()
        except GitEngineError:
            resolved = ""
        if not resolved:
            raise SnapshotNotFoundError(f"Snapshot not found: {snapshot_id}")
        return resolved

    def _get_snapshot(self, commit_id: str) -> SnapshotInfo:
        out = self._run(
            "show", "--no-patch", f"--format={LOG_FORMAT}", commit_id
        ).strip()
        info = self._parse_log_line(out)
        info.branch = self.current_branch()
        return info

    @staticmethod
    def _parse_log_line(line: str) -> SnapshotInfo:
        parts = line.split("\x1f")
        parts += [""] * (4 - len(parts))
        commit_hash, subject, date_str, author = (
            parts[0],
            parts[1],
            parts[2],
            parts[3],
        )
        timestamp = (
            datetime.fromisoformat(date_str) if date_str else datetime.now()
        )
        return SnapshotInfo(
            id=commit_hash,
            message=subject,
            timestamp=timestamp,
            branch="",
            author=author or None,
        )

    # ---- branches -----------------------------------------------------------

    def list_branches(self) -> List[str]:
        out = self._run_repo_only(
            "for-each-ref", "refs/heads/", "--format=%(refname:short)"
        )
        return [line.strip() for line in out.splitlines() if line.strip()]

    def current_branch(self) -> str:
        try:
            return self._run_repo_only(
                "symbolic-ref", "--short", "HEAD"
            ).strip()
        except GitEngineError:
            # Unborn HEAD (no commits yet) or detached state: fall back
            # to the configured default branch instead of a bogus ref.
            head = os.path.join(self.repo_path, "HEAD")
            if not os.path.exists(head):
                return self.branch
            try:
                with open(head) as f:
                    content = f.read().strip()
                if content.startswith("ref:"):
                    return content.split("ref: refs/heads/")[-1]
            except OSError:
                pass
            return self.branch

    def create_branch(
        self, name: str, from_snapshot: Optional[str] = None
    ) -> None:
        if name in self.list_branches():
            raise BranchError(f"Branch already exists: {name}")
        start = from_snapshot or "HEAD"
        self.init()
        self._run_repo_only("branch", name, start)
        logger.info(
            f"[{self.game.name}] Created branch '{name}' from {start[:8]}"
        )

    def switch_branch(
        self, name: str, auto_snapshot_message: Optional[str] = None
    ) -> None:
        current = self.current_branch()
        if name == current:
            return
        if name not in self.list_branches():
            raise BranchError(
                f"Branch '{name}' does not exist. "
                f"Create it first: gsc branch create"
            )
        with self._lock:
            self.init()
            if self.has_changes():
                saved = auto_snapshot_message or (
                    f"auto: pending changes before "
                    f"switching from '{current}'"
                )
                self._run("add", "--all")
                self._run("commit", "--quiet", "-m", saved)
                logger.info(
                    f"[{self.game.name}] Auto-snapshot before branch switch"
                )
            self._run("checkout", name)
            logger.info(
                f"[{self.game.name}] Switched branch '{current}' -> '{name}'"
            )

    # ---- transport support --------------------------------------------------

    def export_history(self, output_path: str) -> None:
        """Serialize complete history (all refs) into a single bundle file."""
        self.init()
        tmp_path = output_path + ".tmp"
        try:
            self._run_repo_only("bundle", "create", tmp_path, "--all")
            os.replace(tmp_path, output_path)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
        logger.debug(
            f"[{self.game.name}] Exported history bundle to {output_path}"
        )

    def import_history(self, artifact_path: str) -> None:
        """
        Merge a previously exported artifact into local history.

        Non-current branches are moved to the imported tips directly
        (last-write-wins). The current branch only fast-forwards; divergence
        is reported and left untouched so no local snapshots are lost.
        """
        self.init()
        staging = "gsc-import"
        self._run_repo_only(
            "fetch",
            "--force",
            artifact_path,
            f"refs/heads/*:refs/remotes/{staging}/*",
        )
        out = self._run_repo_only(
            "for-each-ref",
            f"refs/remotes/{staging}/",
            "--format=%(refname:short)",
        )
        imported = [line.strip() for line in out.splitlines() if line.strip()]
        current = self.current_branch()

        for full_name in imported:
            branch = full_name.split("/", 1)[1]  # strip staging prefix
            remote_id = self._run_repo_only(
                "rev-parse", "--verify", f"refs/remotes/{staging}/{branch}"
            ).strip()
            if branch == current:
                self._fast_forward_current(
                    remote_id, source=f"'{artifact_path}'"
                )
            else:
                self._run_repo_only(
                    "update-ref", f"refs/heads/{branch}", remote_id
                )
                logger.info(
                    f"[{self.game.name}] Updated branch "
                    f"'{branch}' from artifact"
                )

    def _fast_forward_current(self, target_id: str, source: str) -> bool:
        """Advance the active branch to target_id if it is strictly ahead."""
        local_id = self._head_commit()
        if local_id == target_id:
            return False
        ff_possible = False
        if local_id:
            try:
                self._run_repo_only(
                    "merge-base", "--is-ancestor", local_id, target_id
                )
                ff_possible = True
            except GitEngineError:
                ff_possible = False
        else:
            # Unborn HEAD: nothing local to lose, take the imported state.
            ff_possible = True
        if not ff_possible:
            logger.warning(
                f"[{self.game.name}] Local branch '{self.current_branch()}' "
                f"diverged from {source}; skipping fast-forward. Use "
                f"`gsc restore {target_id[:8]} --hard` to force it."
            )
            return False
        with self._lock:
            if local_id and self.has_changes():
                self.snapshot(message="auto: pending changes before pull")
            self._run("reset", "--hard", target_id)
            logger.info(
                f"[{self.game.name}] Fast-forwarded '{self.current_branch()}' "
                f"to {target_id[:8]} from {source}"
            )
            return True

    def _head_commit(self):
        try:
            out = self._run("rev-parse", "--verify", "--quiet", "HEAD").strip()
            return out or None
        except GitEngineError:
            return None

    # ---- status -------------------------------------------------------------

    def status(self) -> Dict:
        self.init()
        changed_files = [
            line[3:]
            for line in self._run("status", "--porcelain").splitlines()
            if line.strip()
        ]
        branches = self.list_branches()
        snapshot_count = 0
        if branches:
            try:
                snapshot_count = len(self.list_snapshots())
            except BranchError:
                snapshot_count = 0
        return {
            "engine": "git",
            "branch": self.current_branch(),
            "branches": branches,
            "dirty": bool(changed_files),
            "changed_files": changed_files,
            "snapshots": snapshot_count,
            "repo_path": self.repo_path,
        }
