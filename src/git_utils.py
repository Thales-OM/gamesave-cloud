import os
import subprocess
import sys
import platform
from src.logger import LoggerFactory


logger = LoggerFactory.getLogger(__name__)


def is_git_installed() -> bool:
    try:
        # Check if git is available
        subprocess.run(['git', '--version'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except Exception:
        return False

def install_git() -> None:
    system = platform.system()
    if system == "Windows":
        # For Windows, you can use Chocolatey to install Git
        logger.info("Installing Git on Windows...")
        subprocess.run(['winget', 'install', '--id', 'Git.Git', '--silent'], check=True)
    elif system == "Linux":
        # For Debian-based systems
        logger.info("Installing Git on Linux...")
        subprocess.run(['apt-get', 'update', '-y'], check=True)
        subprocess.run(['apt-get', 'install', 'git', '-y'], check=True)
    elif system == "Darwin":
        # For macOS, you can use Homebrew
        logger.info("Installing Git on macOS...")
        subprocess.run(['brew', 'install', 'git', '--quiet', '--force'], check=True)
    else:
        raise OSError("Unsupported operating system. Please install Git manually.")
