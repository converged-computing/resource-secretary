from typing import Any, Dict

from ...provider import secretary_tool
from ..base import MockBaseProvider


class MockEthernetProvider(MockBaseProvider):
    """
    Standard Ethernet.
    Scale: Interface Speed (1G vs 10G).
    Density: Number of virtual/physical interfaces.
    """

    def __init__(self, config):
        super().__init__(config)
        self._devices = []
        self.available = False
        self.capability_tools = {"network": ["get_interface_stats"]}

    @property
    def name(self) -> str:
        return "ethernet"

    def probe(self) -> bool:
        # Determine how many interfaces exist (density)
        # High density might include bridge/docker interfaces
        num_ifs = max(1, int(5 * self.config.targets.get("density") or 0.5))
        self._ifaces = [f"eth{i}" for i in range(num_ifs)]

        # Determine speed (Scale)
        self._speed = 10000 if self.config.targets.get("scale", 0.5) > 0.5 else 1000

        self.available = True
        return True

    @property
    def metadata(self) -> Dict[str, Any]:
        return {
            "interface_count": len(self._ifaces),
            "interfaces": self._ifaces,
            "is_local_only": False,
        }

    @secretary_tool
    def get_interface_stats(self) -> Dict[str, Any]:
        """
        psutil.net_if_stats: Mapping of interface names to stats.
        """
        stats = {}
        for iface in self._ifaces:
            stats[iface] = {
                "is_up": True,
                "speed_mbit": self._speed,
                "mtu": 1500 if "eth" in iface else 9000,
            }
        return stats

    def export_truth(self) -> Dict[str, Any]:
        return {"interfaces": self._ifaces, "speed_mbit": self._speed}
