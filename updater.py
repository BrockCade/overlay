import os
import sys
import json
import base64
import subprocess
from pathlib import Path


_GH_PATH = None


def _find_gh():
    candidates = [
        "gh.exe",
        r"C:\Program Files\GitHub CLI\gh.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\GitHubCLI\gh.exe"),
    ]
    for c in candidates:
        try:
            r = subprocess.run([c, "--version"], capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                return c
        except FileNotFoundError:
            continue
    return None


def _gh(args):
    global _GH_PATH
    if _GH_PATH is None:
        _GH_PATH = _find_gh()
        if _GH_PATH is None:
            return None
    try:
        result = subprocess.run(
            [_GH_PATH] + args,
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def get_current_version():
    path = Path(__file__).resolve().parent / "version.txt"
    try:
        return path.read_text().strip()
    except FileNotFoundError:
        return "0.0.0"


def check_remote_version(owner, repo, branch="ai"):
    data = _gh(["api", f"repos/{owner}/{repo}/contents/version.txt?ref={branch}", "--jq", ".content"])
    if data is None:
        return None
    try:
        return base64.b64decode(data).decode().strip()
    except Exception:
        return None


def apply_update(target_dir=None):
    if target_dir is None:
        target_dir = Path(__file__).resolve().parent

    try:
        subprocess.run(["git", "fetch", "origin"], check=True, timeout=30, cwd=target_dir)

        status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=10, cwd=target_dir
        )
        has_uncommitted = bool(status.stdout.strip())

        if has_uncommitted:
            subprocess.run(["git", "stash", "push", "-m", "auto-stash before update"],
                           check=True, timeout=10, cwd=target_dir)

        subprocess.run(
            ["git", "pull", "--ff-only", "origin", "ai"],
            check=True, timeout=30, cwd=target_dir
        )

        pulled_version = None
        version_file = Path(target_dir) / "version.txt"
        if version_file.exists():
            pulled_version = version_file.read_text().strip()

        if has_uncommitted:
            subprocess.run(["git", "stash", "pop"], check=False, timeout=10, cwd=target_dir)
            if pulled_version:
                version_file.write_text(pulled_version)

        new_version = pulled_version or "?"
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
