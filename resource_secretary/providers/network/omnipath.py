import os
import shutil
from typing import Any, Dict, List

from ..provider import secretary_tool
from .network import NetworkProvider


class OmniPathProvider(NetworkProvider):
    """
    Handles discovery and status for Intel Omni-Path (OPA) fabrics.
    """

    is_provider = True

    @property
    def name(self) -> str:
        return "omni-path"

    def probe(self) -> bool:
        """
        Checks for the presence of hfi1 devices in sysfs.
        """
        self.available = self.check_path_exists("/sys/class/hfi1")
        return self.available

    @property
    def metadata(self) -> Dict[str, Any]:
        """
        Returns a list of discovered Omni-Path host fabric interfaces.
        """
        hfi_devices = []
        if self.available:
            try:
                hfi_devices = os.listdir("/sys/class/hfi1")
            except:
                pass
        return {
            "hfi_count": len(hfi_devices),
            "devices": hfi_devices,
            "has_opainfo": shutil.which("opainfo") is not None,
        }

    @secretary_tool
    def get_opa_details(self) -> str:
        """
        Retrieves detailed OPA fabric statistics and link states using opainfo.

        Returns:
            str: Detailed hardware status of the Omni-Path fabric.
        """
        tool = shutil.which("opainfo")
        if tool:
            return self.run_network_cmd([tool])
        return "opainfo binary not found."
