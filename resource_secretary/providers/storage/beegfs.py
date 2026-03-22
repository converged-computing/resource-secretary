import shutil
from typing import Any, Dict

from ..provider import secretary_tool
from .storage import StorageProviderBase


class BeeGFSProvider(StorageProviderBase):
    """
    Handles discovery and status for BeeGFS parallel filesystems.
    """

    is_provider = True

    @property
    def name(self) -> str:
        return "beegfs"

    def probe(self) -> bool:
        """
        Checks for beegfs mounts and the beegfs-ctl utility.
        """
        self.mount_point = self.find_mount_by_type("beegfs")
        return self.mount_point is not None and shutil.which("beegfs-ctl") is not None

    @property
    def metadata(self) -> Dict[str, Any]:
        """
        Returns the mount point and beegfs status.
        """
        return {"mount_point": self.mount_point, "has_ctl": shutil.which("beegfs-ctl") is not None}

    @secretary_tool
    def get_storage_stats(self) -> str:
        """
        Retrieves global storage statistics (capacity and usage) for the BeeGFS cluster.

        Returns:
            str: Summary of storage targets and their health.
        """
        return self.run_storage_cmd(["beegfs-ctl", "--listtargets", "--state"])
