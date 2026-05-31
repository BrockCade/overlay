import os
import sys
import subprocess
import urllib.request
import urllib.error
from pathlib import Path


def get_current_version():
    path = Path(__file__).resolve().parent / "version.txt"
    try:
        return path.read_text().strip()
    except FileNotFoundError:
        return "0.0.0"


def check_remote_version(owner, repo, branch="ai"):
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/version.txt"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.read().decode().strip()
    except (urllib.error.URLError, urllib.error.HTTPError):
        return None


def apply_update(target_dir=None):
    if target_dir is None:
        target_dir = Path(__file__).resolve().parent

    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=10,
            cwd=target_dir
        )
        if result.stdout.strip():
            return {"success": False, "error": "uncommitted_changes"}

        subprocess.run(["git", "fetch", "origin"], check=True, timeout=30, cwd=target_dir)
        subprocess.run(
            ["git", "pull", "--ff-only", "origin", "ai"],
            check=True, timeout=30, cwd=target_dir
        )

        version_file = Path(target_dir) / "version.txt"
        new_version = version_file.read_text().strip() if version_file.exists() else "?"
        return {"success": True, "updated": True, "version": new_version}

    except subprocess.CalledProcessError as e:
        return {"success": False, "error": str(e)}
    except FileNotFoundError:
        return {"success": False, "error": "git_not_found"}


def restart_app():
    python = sys.executable
    script = Path(__file__).resolve().parent / "main.py"
    subprocess.Popen([python, str(script)])
    sys.exit(0)
