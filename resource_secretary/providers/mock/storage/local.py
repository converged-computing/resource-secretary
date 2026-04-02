from typing import Any, Dict

from ...provider import secretary_tool
from ..base import MockBaseProvider


class MockLocalScratchProvider(MockBaseProvider):
    """
    Local Scratch (NVMe/SSD).
    """

    def probe(self) -> bool:
        rng = self.config.get_rng("local_scratch")
        self.mount = rng.choice(["/tmp", "/mnt/local_ssd", "/scratch/local"])
        self.fs_type = rng.choice(["xfs", "ext4", "zfs"])
        self.size_gb = rng.randint(100, 2000)
        self.available = True
        return True

    @property
    def name(self) -> str:
        return "local-scratch"

    @secretary_tool
    def get_scratch_details(self) -> Dict[str, Any]:
        """
        Returns details on local high-speed scratch space.
        """
        return {
            "mount": self.mount,
            "fstype": self.fs_type,
            "size_gb": self.size_gb,
            "io_profile": "high-iops",
        }

    def export_truth(self):
        return {"mount": self.mount, "size_gb": self.size_gb}
