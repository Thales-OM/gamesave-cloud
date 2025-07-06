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


def git_pull_accept_remote(directory_path):
    """
    Perform git pull in the specified directory, resolving conflicts in
    favor of remote changes without changing the current working directory
    of the main program.

    Args:
        directory_path (str): Path to the git repository directory

    Returns:
        bool: True if successful, False if failed
    """
    try:
        # Convert to absolute path and verify it's a directory
        repo_path = Path(directory_path).absolute()
        if not repo_path.is_dir():
            raise FileNotFoundError(
                f"Error: {directory_path} is not a valid directory"
            )

        # Check if this is a git repository
        if not (repo_path / ".git").is_dir():
            raise GitError(f"Error: {directory_path} is not a git repository")

        logger.info(f"Performing git pull in {repo_path}...")

        # First try a normal pull
        try:
            subprocess.run(["git", "pull"], cwd=repo_path, check=True)
            logger.info("Git pull completed successfully")
            return True
        except subprocess.CalledProcessError as e:
            logger.warning(
                f"Normal pull failed, attempting to resolve \
                    conflicts in favor of remote...\n{e}"
            )

            # If normal pull fails, try with merge strategy
            # favoring remote changes
            try:
                # Fetch all changes first
                subprocess.run(
                    ["git", "fetch", "--all"], cwd=repo_path, check=True
                )

                # Reset to remote branch, accepting all remote changes
                subprocess.run(
                    ["git", "reset", "--hard", "HEAD"],
                    cwd=repo_path,
                    check=True,
                )
                subprocess.run(
                    ["git", "pull", "-X", "theirs"], cwd=repo_path, check=True
                )

                logger.info(
                    "Successfully resolved conflicts in \
                        favor of remote repository"
                )
                return True
            except subprocess.CalledProcessError as e:
                raise GitError(f"Failed to resolve conflicts: {e}")

    except Exception as e:
        raise GitError(f"An unexpected error occurred: {e}")
