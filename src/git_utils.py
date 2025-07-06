import os
import subprocess
import platform
from pathlib import Path
from src.exceptions import GitError
from src.logger import LoggerFactory

logger = LoggerFactory.getLogger(__name__)


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


def install_git() -> None:
    system = platform.system()
    if system == "Windows":
        # For Windows, you can use Chocolatey to install Git
        logger.info("Installing Git on Windows...")
        subprocess.run(
            ["winget", "install", "--id", "Git.Git", "--silent"], check=True
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


def check_git_repository(path: str) -> bool:
    # Check if the directory exists
    if not os.path.isdir(path):
        raise FileNotFoundError(
            f"Expected local repository path {path} does not exist."
        )
    # Check if it's a git repository
    try:
        subprocess.run(
            ["git", "-C", path, "rev-parse", "--is-inside-work-tree"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def create_git_repository(path: str) -> None:
    # Create a new git repository
    subprocess.run(["git", "-C", path, "init"], check=True)
    logger.info(f"Created a new git repository at {path}.")


def create_master_branch(path: str, master_branch: str = "master") -> None:
    # Create a master branch from the current HEAD
    subprocess.run(
        ["git", "-C", path, "checkout", "-b", master_branch], check=True
    )
    logger.info("Created a master branch from the current HEAD.")


def git_pull_with_conflict_resolution(
    repo_dir: str,
    remote_name: str = "origin",
    remote_branch: str = None,
    local_branch: str = None,
    favor_remote: bool = True,
) -> None:
    """
    Perform git pull with conflict resolution options.

    Args:
        repo_dir: Path to the local git repository
        remote_name: Name of the remote (default: 'origin')
        remote_branch: Remote branch name (default: current local
            branch's upstream)
        local_branch: Local branch name (default: current branch)
        favor_remote: Whether to resolve conflicts in favor of
            remote (default: True)

    Returns:
        None
    """
    try:
        repo_path = Path(repo_dir).absolute()

        # Validate directory and repository
        if not repo_path.is_dir():
            raise FileNotFoundError(
                f"Error: {repo_dir} is not a valid directory"
            )
        if not check_git_repository(path=str(repo_dir)):
            raise GitError(f"Error: {repo_dir} is not a git repository")

        # Get current branch if not specified
        if not local_branch:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )
            local_branch = result.stdout.strip()
            if not local_branch:
                raise GitError("Error: Could not determine current branch")

        # Get remote branch if not specified
        if not remote_branch:
            result = subprocess.run(
                ["git", "config", "--get", f"branch.{local_branch}.merge"],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )
            remote_branch = result.stdout.strip().replace("refs/heads/", "")
            if not remote_branch:
                remote_branch = local_branch  # Fallback to same name as local

        logger.info(
            f"Pulling {remote_name}/{remote_branch} into {local_branch}..."
        )

        # First try normal pull
        try:
            pull_cmd = [
                "git",
                "pull",
                remote_name,
                f"{remote_branch}:{local_branch}",
            ]
            subprocess.run(pull_cmd, cwd=repo_path, check=True)
            logger.info("Git pull completed successfully")
        except subprocess.CalledProcessError as e:
            logger.warning(
                f"Normal pull failed, attempting conflict resolution...\n{e}"
            )

            try:
                # Fetch updates
                subprocess.run(
                    ["git", "fetch", remote_name], cwd=repo_path, check=True
                )

                if favor_remote:
                    # Reset to remote version
                    reset_cmd = [
                        "git",
                        "reset",
                        "--hard",
                        f"{remote_name}/{remote_branch}",
                    ]
                    subprocess.run(reset_cmd, cwd=repo_path, check=True)
                    logger.info("Reset to remote version successfully")
                else:
                    # Try merge with strategy option
                    merge_cmd = [
                        "git",
                        "merge",
                        f"{remote_name}/{remote_branch}",
                        "-X",
                        "theirs" if favor_remote else "ours",
                    ]
                    subprocess.run(merge_cmd, cwd=repo_path, check=True)
                    logger.info("Merge with conflict resolution completed")
            except subprocess.CalledProcessError as e:
                raise GitError(f"Conflict resolution failed: {e}")
    except Exception as e:
        raise GitError(f"An unexpected error occurred: {e}")
