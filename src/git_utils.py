import os
import subprocess
import platform
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
