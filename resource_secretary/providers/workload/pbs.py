import os
import shutil
from typing import Any, Dict

from ..provider import secretary_tool
from .workload import WorkloadProviderBase


class PBSProvider(WorkloadProviderBase):
    """
    Handles discovery and status for OpenPBS and PBS Pro.
    """

    is_provider = True

    @property
    def name(self) -> str:
        return "pbs"

    def probe(self) -> bool:
        """
        Checks for qsub and ensures it is not a Cobalt environment.
        """
        self.bin_path = shutil.which("qsub")
        return self.bin_path is not None and "COBALT_JOBID" not in os.environ

    @property
    def metadata(self) -> Dict[str, Any]:
        """
        Returns PBS server information.
        """
        return {"server": os.environ.get("PBS_SERVER", "unknown")}

    @secretary_tool
    def get_job_list(self) -> str:
        """
        Retrieves all jobs currently in the PBS queue.

        Returns:
            str: Output of 'qstat -a'.
        """
        return self.run_workload_cmd(["qstat", "-a"])
