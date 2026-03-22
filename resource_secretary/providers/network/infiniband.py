import os
import shutil
from typing import Any, Dict, List

from ..provider import secretary_tool
from .network import NetworkProvider


class InfiniBandProvider(NetworkProvider):
    """
    Handles discovery and status for InfiniBand and RDMA fabrics.
    """

    is_provider = True

    @property
    def name(self) -> str:
        return "infiniband"

    def probe(self) -> bool:
        """
        Checks for the existence of the infiniband class in sysfs.
        """
        self.available = self.check_path_exists("/sys/class/infiniband")
        return self.available

    @property
    def metadata(self) -> Dict[str, Any]:
        """
        Returns a list of discovered HCA devices.
        """
        devices = []
        if self.available:
            try:
                devices = os.listdir("/sys/class/infiniband")
            except:
                pass
        return {
            "device_count": len(devices),
            "devices": devices,
            "has_ibstat": shutil.which("ibstat") is not None,
        }

    @secretary_tool
    def get_port_status(self) -> str:
        """
        Retrieves detailed port states and speeds using ibstat or ibv_devinfo.

        Returns:
            str: Detailed hardware status of the RDMA fabric.
        """
        tool = shutil.which("ibstat") or shutil.which("ibv_devinfo")
        if tool:
            return self.run_network_cmd([tool])
        return "No InfiniBand diagnostic tools (ibstat/ibv_devinfo) found."
