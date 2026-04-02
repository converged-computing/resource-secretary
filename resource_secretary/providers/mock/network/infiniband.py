import random
from typing import Any, Dict, List

from ...provider import secretary_tool
from ..base import MockBaseProvider


class MockInfiniBandProvider(MockBaseProvider):
    """
    InfiniBand / RDMA Fabric.
    Scale: Link Speed (EDR/HDR/NDR).
    Density: Device count and port complexity.
    """

    def __init__(self, config):
        super().__init__(config)
        self._devices = []
        self._speed = "100 Gbps"
        self.available = False

    @property
    def name(self) -> str:
        return "infiniband"

    def probe(self) -> bool:

        # Speed (scale)
        # High scale workers get NDR/HDR; Low scale get EDR or QDR
        speed_options = ["40 Gbps (QDR)", "100 Gbps (EDR)", "200 Gbps (HDR)", "400 Gbps (NDR)"]
        speed_idx = min(
            len(speed_options) - 1,
            int(len(speed_options) * self.config.targets.get("scale") or 0.5),
        )
        self._speed = speed_options[speed_idx]

        # Density (device count)
        # Most systems have 1, some have 2 or 4 HCAs
        dev_count = self.generate("network_devices", mode="density", volatility=0.1)
        dev_count = max(1, min(4, dev_count))

        self._devices = [f"mlx5_{i}" for i in range(dev_count)]
        self.available = True
        return True

    @property
    def metadata(self) -> Dict[str, Any]:
        return {
            "device_count": len(self._devices),
            "devices": self._devices,
            "has_ibstat": True,
            "max_speed": self._speed,
        }

    @secretary_tool
    def get_port_status(self) -> str:
        """
        ibstat: Retrieves detailed port states and speeds.
        """
        lines = []
        for dev in self._devices:
            lines.append(f"CA '{dev}'")
            lines.append(f"\tCA type: MT4123 Family")
            lines.append(f"\tNumber of ports: 1")
            lines.append(f"\tPort 1:")
            lines.append(f"\t\tState: Active")
            lines.append(f"\t\tPhysical state: LinkUp")
            lines.append(f"\t\tRate: {self._speed}")
            lines.append(f"\t\tBase lid: {random.randint(1, 100)}")
            lines.append(f"\t\tLMC: 0")
            lines.append(f"\t\tSM lid: 1")
            lines.append(f"\t\tCapability mask: 0x2651e84a")
            lines.append("")
        return "\n".join(lines)

    def export_truth(self) -> Dict[str, Any]:
        return {"devices": self._devices, "speed": self._speed}
