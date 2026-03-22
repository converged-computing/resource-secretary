import os
import subprocess
from typing import Any, Dict, List, Optional

from ..provider import BaseProvider


class StorageProviderBase(BaseProvider):
    """
    Intermediate logic for filesystem discovery and interaction.
    """

    is_provider = False

    def __init__(self):
        super().__init__()
        self.mount_point: Optional[str] = None

    def get_mounts(self) -> List[str]:
        """
        Reads /proc/mounts and returns a list of raw mount lines.
        """
        if not os.path.exists("/proc/mounts"):
            return []
        try:
            with open("/proc/mounts", "r") as f:
                return f.readlines()
        except:
            return []

    def find_mount_by_type(self, fs_type: str) -> Optional[str]:
        """
        Returns the first mount point found for a specific filesystem type.
        """
        for line in self.get_mounts():
            parts = line.split()
            if len(parts) > 2 and parts[2] == fs_type:
                return parts[1]
        return None

    def run_storage_cmd(self, cmd: List[str]) -> str:
        """
        Executes a filesystem specific utility command.
        """
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
        except Exception as e:
            return f"Error executing tool {cmd[0]}: {str(e)}"
