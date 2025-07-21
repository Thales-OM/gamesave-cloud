import subprocess
import platform
from typing import List, Tuple
from datetime import datetime
import pytz
from git import Repo
from src.exceptions import GitError
from src.logger import LoggerFactory

logger = LoggerFactory.getLogger(__name__)


class GitUtils:
    @staticmethod
    def is_git_installed() -> bool:
        try:
            # Check if git is available
            subprocess.run(
                ["git", "--version"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            return True
        except subprocess.CalledProcessError:
            return False

    @staticmethod
    def install_git() -> None:
        system = platform.system()
        if system == "Windows":
            # For Windows, you can use Chocolatey to install Git
            logger.info("Installing Git on Windows...")
            subprocess.run(
                ["winget", "install", "--id", "Git.Git", "--silent"],
                check=True,
            )
        elif system == "Linux":
            # For Debian-based systems
            logger.info("Installing Git on Linux...")
            subprocess.run(["apt-get", "update", "-y"], check=True)
            subprocess.run(["apt-get", "install", "git", "-y"], check=True)
        elif system == "Darwin":
            # For macOS, you can use Homebrew
            logger.info("Installing Git on macOS...")
            subprocess.run(
                ["brew", "install", "git", "--quiet", "--force"], check=True
            )
        else:
            raise OSError(
                "Unsupported operating system. Please install Git manually."
            )

    @staticmethod
    def is_git_repo(path: str) -> bool:
        try:
            _ = Repo(path).git_dir
            return True
        except Exception:
            return False

    @staticmethod
    def init_repo(path: str) -> Repo:
        if GitUtils.is_git_repo(path):
            return Repo(path)
        return Repo.init(path)

    @staticmethod
    def get_repo(path: str) -> Repo:
        if not GitUtils.is_git_repo(path):
            raise GitError(f"No git repo found at {path}")
        return Repo(path)

    @staticmethod
    def branch_exists(repo: Repo, branch_name: str) -> bool:
        return branch_name in [h.name for h in repo.heads]

    @staticmethod
    def create_orphan_branch(repo: Repo, branch_name: str):
        # Create orphan branch: no parents, empty history
        git = repo.git
        git.checkout("--orphan", branch_name)
        # Remove all files from index
        git.rm("-rf", ".")
        # Commit empty tree to start branch
        repo.index.commit(f"Orphan branch {branch_name} created")

    @staticmethod
    def checkout_branch(repo: Repo, branch_name: str):
        if GitUtils.branch_exists(repo, branch_name):
            repo.git.checkout(branch_name)

    @staticmethod
    def has_uncommitted_changes(repo: Repo) -> bool:
        return repo.is_dirty(untracked_files=True)

    @staticmethod
    def commit_all(repo: Repo, message: str):
        repo.git.add(all=True)
        if GitUtils.has_uncommitted_changes(repo):
            repo.index.commit(message)

    @staticmethod
    def get_current_branch(repo: Repo) -> str:
        return repo.active_branch.name

    @staticmethod
    def set_remote(repo: Repo, remote_name: str, url: str):
        try:
            remote = repo.remote(remote_name)
            remote.set_url(url)
        except ValueError:
            repo.create_remote(remote_name, url)

    @staticmethod
    def fetch_remote(repo: Repo, remote_name: str):
        repo.remotes[remote_name].fetch()

    @staticmethod
    def delete_local_branch(repo: Repo, branch_name: str):
        if GitUtils.branch_exists(repo, branch_name):
            repo.git.branch("-D", branch_name)

    @staticmethod
    def reset_branch_to_commit(repo: Repo, branch_name: str, commit_id: str):
        # Hard reset branch to commit_id
        repo.git.reset("--hard", commit_id)

    @staticmethod
    def revert_to_commit(repo: Repo, commit_id: str, message: str):
        # Create a new commit that reverts to the state of commit_id
        # without losing history
        repo.git.reset("--soft", commit_id)
        repo.git.add(all=True)
        repo.index.commit(message)

    @staticmethod
    def get_commits(
        repo: Repo, branch_name: str
    ) -> List[Tuple[str, str, datetime]]:
        commits = []
        for commit in repo.iter_commits(branch_name):
            dt = datetime.fromtimestamp(commit.committed_date, pytz.utc)
            commits.append((commit.hexsha, commit.message.strip(), dt))
        return commits

    @staticmethod
    def mirror_remote_to_local(repo: Repo, remote_name: str, branch_name: str):
        # Delete local branch if exists
        if GitUtils.branch_exists(repo, branch_name):
            repo.git.branch("-D", branch_name)
        # Fetch remote branch
        GitUtils.fetch_remote(repo, remote_name)
        # Create local branch tracking remote branch
        repo.git.checkout("-b", branch_name, f"{remote_name}/{branch_name}")

    @staticmethod
    def mirror_local_to_remote(repo: Repo, remote_name: str, branch_name: str):
        # Force push local branch to remote
        repo.git.push(remote_name, f"{branch_name}:{branch_name}", force=True)
