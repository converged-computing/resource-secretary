from typing import Any, Dict

from ...provider import secretary_tool
from ..base import MockBaseProvider


class MockLustreProvider(MockBaseProvider):
    """
    Expert Mock: Lustre Parallel Filesystem.
    Scale Anchor: Total Capacity (TB/PB).
    Density Anchor: Utilization Percentage.
    """

    def __init__(self, config):
        super().__init__(config)
        self.mount = f"/scratch/{self.config.system_name}"
        self.available = False

    @property
    def name(self) -> str:
        return "lustre"

    def probe(self) -> bool:
        rng = self.config.get_rng("lustre")

        # Generate Capacity (Scale driven, Low Volatility)
        self.size_gb = self.generate("storage_gb", mode="scale", volatility=0.1)

        # Generate Usage (Density driven, High Volatility)
        # Messy clusters (high density) tend to have fuller disks.
        usage_factor = self.config.targets["density"] * rng.uniform(0.5, 1.2)
        self.used_gb = int(self.size_gb * min(0.98, usage_factor))

        self.available = True
        return True

    @property
    def metadata(self) -> Dict[str, Any]:
        return {
            "mount": self.mount,
            "size_gb": self.size_gb,
            "used_gb": self.used_gb,
            "status": "online",
        }

    @secretary_tool
    def get_storage_info(self) -> str:
        """
        Retrieves capacity and usage statistics for Lustre.
        Returns the raw string output of 'lfs df -h'.
        """
        # Mimic the actual output of the Lustre CLI
        used_pct = int((self.used_gb / self.size_gb) * 100)
        free_gb = self.size_gb - self.used_gb

        header = f"{'UUID':<25} {'bytes':<10} {'Used':<10} {'Avail':<10} {'Use%':<5} {'Mounted on'}"
        row = f"{'lustre-MDT0000_UUID':<25} {self.size_gb:>8}G {self.used_gb:>8}G {free_gb:>8}G {used_pct:>3}% {self.mount}"
        return f"{header}\n{row}"

    def export_truth(self) -> Dict[str, Any]:
        return {"mount": self.mount, "size_gb": self.size_gb, "used_gb": self.used_gb}
