import os
import shutil
from typing import Any, Dict

from ..provider import secretary_tool
from .workload import WorkloadProviderBase


class TorqueProvider(WorkloadProviderBase):
    """
    Handles discovery for the Torque resource manager.
    """

    is_provider = True

    @property
    def name(self) -> str:
        return "torque"

    def probe(self) -> bool:
        """
        Checks for Torque specific paths or binaries.
        """
        self.bin_path = shutil.which("qsub")
        return self.bin_path is not None and os.path.exists("/var/spool/torque")

    @property
    def metadata(self) -> Dict[str, Any]:
        """
        Returns Torque installation status.
        """
        return {"status": "active" if self.bin_path else "missing"}

    @secretary_tool
    def get_node_status(self) -> str:
        """
        Retrieves the status of all nodes in the Torque cluster.

        Returns:
            str: Output of 'pbsnodes -a'.
        """
        tool = shutil.which("pbsnodes")
        return self.run_workload_cmd([tool, "-a"]) if tool else "pbsnodes not found"
