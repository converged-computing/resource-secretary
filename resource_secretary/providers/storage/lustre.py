import shutil
from typing import Any, Dict

from ..provider import secretary_tool
from .storage import StorageProviderBase


class LustreProvider(StorageProviderBase):
    """
    Handles discovery and status for Lustre parallel filesystems.
    """

    is_provider = True

    @property
    def name(self) -> str:
        return "lustre"

    def probe(self) -> bool:
        """
        Checks for lustre mounts and the lfs utility.
        """
        self.mount_point = self.find_mount_by_type("lustre")
        return self.mount_point is not None and shutil.which("lfs") is not None

    @property
    def metadata(self) -> Dict[str, Any]:
        """
        Returns the primary mount point and lfs version.
        """
        return {
            "mount_point": self.mount_point,
            "lfs_version": self.run_storage_cmd(["lfs", "--version"]),
        }

    @secretary_tool
    def get_quota_info(self, path: str) -> str:
        """
        Retrieves the quota and usage for a specific path on the Lustre filesystem.

        Inputs:
            path (str): The directory to check (e.g., '/scratch/user').

        Returns:
            str: Output of 'lfs quota'. Use this to verify if there is
                 enough remaining space for job outputs.
        """
        return self.run_storage_cmd(["lfs", "quota", "-h", path])

    @secretary_tool
    def get_stripe_info(self, path: str) -> str:
        """
        Retrieves the striping configuration for a file or directory.

        Inputs:
            path (str): The path to investigate.

        Returns:
            str: Striping details. Use this to verify if the I/O pattern
                 is optimized for large parallel writes.
        """
        return self.run_storage_cmd(["lfs", "getstripe", path])
