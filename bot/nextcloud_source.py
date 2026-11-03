import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

import requests

from . import config
from .source_base import FileSource

DAV_NS = "{DAV:}"


class NextcloudSource(FileSource):
    def __init__(self):
        self.username = config.NEXTCLOUD_USERNAME
        self.password = config.NEXTCLOUD_PASSWORD
        self.remote_path = config.NEXTCLOUD_PATH.strip("/")
        self.cache_dir = Path(config.NEXTCLOUD_CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_file = self.cache_dir / ".manifest.json"
        self._stored_manifest: dict[str, str] = {}
        self._base_url = config.NEXTCLOUD_URL.rstrip("/")
        self._dav_root = (
            f"{self._base_url}/remote.php/dav/files/{self.username}/{self.remote_path}"
        )
        self._load_manifest()

    @property
    def base_dir(self) -> Path:
        return self.cache_dir

    def _load_manifest(self):
        if self._manifest_file.exists():
            try:
                self._stored_manifest = json.loads(self._manifest_file.read_text())
            except (json.JSONDecodeError, OSError):
                self._stored_manifest = {}

    def _save_manifest(self, manifest: dict[str, str]):
        self._manifest_file.write_text(json.dumps(manifest, indent=2))

    def _compute_marker(self, manifest: dict[str, str]) -> str:
        raw = json.dumps(manifest, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def _list_remote(self) -> dict[str, str]:
        headers = {"Depth": "infinity"}
        resp = requests.request(
            "PROPFIND", self._dav_root,
            auth=(self.username, self.password),
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()

        root = ET.fromstring(resp.content)
        prefix = self._dav_root + "/"
        files: dict[str, str] = {}

        for response in root.iter(f"{DAV_NS}response"):
            href = response.find(f"{DAV_NS}href")
            if href is None or not href.text:
                continue
            path = href.text
            if not path.startswith(prefix):
                continue
            rel = path[len(prefix):]
            if not rel or not rel.endswith(".md"):
                continue

            prop = response.find(f"{DAV_NS}propstat/{DAV_NS}prop")
            if prop is None:
                continue
            etag_el = prop.find(f"{DAV_NS}getetag")
            if etag_el is None or not etag_el.text:
                continue

            files[rel] = etag_el.text.strip('"')

        return files

    def _download_file(self, rel_path: str):
        url = f"{self._dav_root}/{rel_path}"
        resp = requests.get(url, auth=(self.username, self.password), timeout=30)
        resp.raise_for_status()

        local = self.cache_dir / rel_path
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(resp.content)

    def poll(self, last_marker: Optional[str]) -> tuple[bool, str, list[Path]]:
        try:
            current = self._list_remote()
            marker = self._compute_marker(current)

            if marker == last_marker:
                return True, marker, []

            changed = []
            for rel, etag in current.items():
                if self._stored_manifest.get(rel) != etag:
                    changed.append(rel)

            for rel in changed:
                self._download_file(rel)

            self._save_manifest(current)
            self._stored_manifest = current

            local = [self.cache_dir / rel for rel in changed]
            return True, marker, local
        except Exception as e:
            print(f"Nextcloud poll error: {e}")
            return False, last_marker or "", []
