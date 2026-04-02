from typing import Any, Dict

from ...provider import secretary_tool
from ..base import MockBaseProvider


class MockNFSProvider(MockBaseProvider):
    """
    Network File System (NFS).
    """

    def __init__(self, config):
        super().__init__(config)
        self.mount = "/home"
        self.host = f"nfs-server-{self.config.seed}.local"

    def probe(self) -> bool:
        self.size_gb = self.generate("storage_gb", mode="scale", volatility=0.3) // 10
        self.available = True
        return True

    @property
    def name(self) -> str:
        return "nfs"

    @secretary_tool
    def get_nfs_stats(self) -> Dict[str, Any]:
        """
        Retrieves mount point and export details for NFS.
        """
        return {
            "export": f"{self.host}:/exports/home",
            "mount": self.mount,
            "options": "rw,relatime,vers=4.2,rsize=1048576,wsize=1048576,namlen=255,hard,proto=tcp",
            "size_gb": self.size_gb,
        }

    def export_truth(self):
        return {"mount": self.mount, "host": self.host}
