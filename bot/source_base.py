from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class FileSource(ABC):
    @property
    @abstractmethod
    def base_dir(self) -> Path:
        """Local directory where synced files can be read."""

    @abstractmethod
    def poll(self, last_marker: Optional[str]) -> tuple[bool, str, list[Path]]:
        """
        Check remote for changes, download new/modified files locally.

        Args:
            last_marker: previous state marker (None = first run).

        Returns:
            (success, new_marker, list_of_changed_md_file_paths)
        """
