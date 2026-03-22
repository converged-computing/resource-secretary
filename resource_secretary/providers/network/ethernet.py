from typing import Any, Dict, List

import psutil

from ..provider import secretary_tool
from .network import NetworkProvider


class EthernetProvider(NetworkProvider):
    """
    Handles discovery and status for standard Ethernet interfaces.
    """

    is_provider = True

    @property
    def name(self) -> str:
        return "ethernet"

    def probe(self) -> bool:
        """
        Checks for any active non-loopback network interfaces.
        """
        interfaces = psutil.net_if_addrs()
        for interface in interfaces:
            if interface != "lo":
                self.available = True
                return True
        return False

    @property
    def metadata(self) -> Dict[str, Any]:
        """
        Returns active interface counts and connectivity status.
        """
        interfaces = psutil.net_if_addrs()
        active_names = [i for i in interfaces if i != "lo"]
        return {
            "interface_count": len(active_names),
            "interfaces": active_names,
            "is_local_only": len(active_names) == 0,
        }

    @secretary_tool
    def get_interface_stats(self) -> Dict[str, Any]:
        """
        Retrieves real-time packet and error statistics for Ethernet interfaces.

        Returns:
            Dict: Mapping of interface names to their byte/packet counts.
        """
        stats = {}
        for interface, data in psutil.net_if_stats().items():
            stats[interface] = {"is_up": data.isup, "speed_mbit": data.speed, "mtu": data.mtu}
        return stats
