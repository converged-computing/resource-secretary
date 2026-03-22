import shutil
from typing import Any, Dict, List

import psutil

from ..provider import secretary_tool
from .storage import StorageProviderBase


class LocalScratchProvider(StorageProviderBase):
    """
    Identifies high-speed local filesystems (XFS, ZFS, BTRFS) used for local scratch.
    """

    is_provider = True

    @property
    def name(self) -> str:
        return "local-scratch"

    def probe(self) -> bool:
        """
        Looks for high-speed local filesystems typically used for scratch.
        """
        for part in psutil.disk_partitions():
            if part.fstype in ["xfs", "zfs", "btrfs"] and "/scratch" in part.mountpoint:
                self.mount_point = part.mountpoint
                return True
        return False

    @property
    def metadata(self) -> Dict[str, Any]:
        """
        Returns the primary local scratch mount and its filesystem type.
        """
        for part in psutil.disk_partitions():
            if part.mountpoint == self.mount_point:
                return {"path": self.mount_point, "type": part.fstype}
        return {}

    @secretary_tool
    def get_local_capacity(self) -> Dict[str, Any]:
        """
        Retrieves disk usage for the local scratch space.

        Returns:
            Dict: Total, used, and free space in GB. Use this to verify
                  if there is enough local node storage for large datasets.
        """
        usage = psutil.disk_usage(self.mount_point)
        return {
            "total_gb": round(usage.total / (1024**3), 2),
            "free_gb": round(usage.free / (1024**3), 2),
            "percent": usage.percent,
        }
