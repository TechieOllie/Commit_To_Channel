import subprocess
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, urlunparse

from . import config
from .source_base import FileSource


class GitSource(FileSource):
    def __init__(self):
        self.repo_dir = Path(config.CLONE_DIR)

    @property
    def base_dir(self) -> Path:
        return self.repo_dir

    @property
    def _auth_url(self) -> str:
        if not config.GITEA_TOKEN:
            return config.GIT_REPO_URL
        parsed = urlparse(config.GIT_REPO_URL)
        auth_netloc = f"{config.GIT_USERNAME}:{config.GITEA_TOKEN}@{parsed.hostname}"
        if parsed.port:
            auth_netloc += f":{parsed.port}"
        return urlunparse(parsed._replace(netloc=auth_netloc))

    def _clone(self) -> bool:
        self.repo_dir.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["git", "clone", "--filter=blob:none", self._auth_url, str(self.repo_dir)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"Clone failed: {result.stderr.strip()}")
            return False
        return True

    def _fetch_and_reset(self) -> bool:
        if config.GITEA_TOKEN:
            subprocess.run(
                ["git", "-C", str(self.repo_dir), "remote", "set-url", "origin", self._auth_url],
                capture_output=True,
            )
        fetch = subprocess.run(
            ["git", "-C", str(self.repo_dir), "fetch", "--quiet", "origin"],
            capture_output=True, text=True,
        )
        if fetch.returncode != 0:
            print(f"Fetch failed: {fetch.stderr.strip()}")
            return False
        reset = subprocess.run(
            ["git", "-C", str(self.repo_dir), "reset", "--hard", "@{u}"],
            capture_output=True, text=True,
        )
        if reset.returncode != 0:
            print(f"Reset failed: {reset.stderr.strip()}")
            return False
        return True

    def poll(self, last_marker: Optional[str]) -> tuple[bool, str, list[Path]]:
        try:
            if self.repo_dir.exists():
                if not self._fetch_and_reset():
                    return False, last_marker or "", []
            else:
                if not self._clone():
                    return False, last_marker or "", []

            current = self._current_commit()
            if current == last_marker:
                return True, current, []

            files = self._changed_md_files(last_marker)
            return True, current, files
        except Exception as e:
            print(f"Git poll error: {e}")
            return False, last_marker or "", []

    def _current_commit(self) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.repo_dir), "rev-parse", "HEAD"],
            capture_output=True, text=True,
        )
        return result.stdout.strip()

    def _changed_md_files(self, since: Optional[str]) -> list[Path]:
        if since:
            result = subprocess.run(
                ["git", "-C", str(self.repo_dir), "diff", "--name-only", since, "HEAD"],
                capture_output=True, text=True,
            )
            changed = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        else:
            result = subprocess.run(
                ["git", "-C", str(self.repo_dir), "ls-files"],
                capture_output=True, text=True,
            )
            changed = [l.strip() for l in result.stdout.splitlines() if l.strip()]

        md_files = []
        for f in changed:
            if not f.endswith(".md"):
                continue
            if config.WATCHED_DIRECTORY and not f.startswith(config.WATCHED_DIRECTORY):
                continue
            md_files.append(self.repo_dir / f)
        return sorted(md_files)
