from typing import Any, Dict, List

from ..provider import secretary_tool
from .storage import StorageProviderBase


class NetworkFSProvider(StorageProviderBase):
    """
    Handles discovery for standard network filesystems (NFS, CIFS).
    """

    is_provider = True

    @property
    def name(self) -> str:
        return "network-fs"

    def probe(self) -> bool:
        """
        Checks for common network filesystem mounts.
        """
        for fs in ["nfs", "nfs4", "cifs", "smb3"]:
            self.mount_point = self.find_mount_by_type(fs)
            if self.mount_point:
                return True
        return False

    @property
    def metadata(self) -> Dict[str, Any]:
        """
        Returns a list of all active network mounts.
        """
        mounts = []
        for line in self.get_mounts():
            parts = line.split()
            if len(parts) > 2 and parts[2] in ["nfs", "nfs4", "cifs", "smb3"]:
                mounts.append({"path": parts[1], "type": parts[2]})
        return {"mounts": mounts}

    @secretary_tool
    def get_mount_latency_hint(self, path: str) -> str:
        """
        Provides a basic check on the responsiveness of a network mount.

        Inputs:
            path (str): The mount path to test.

        Returns:
            str: Success or timeout message. Use this to verify if
                 a network mount is 'stale' or hanging.
        """
        import subprocess

        try:
            subprocess.run(["ls", path], capture_output=True, timeout=2)
            return f"Mount {path} is responsive."
        except subprocess.TimeoutExpired:
            return f"Mount {path} is hanging/stale."
