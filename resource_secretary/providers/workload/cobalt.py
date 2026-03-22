import os
import shutil
from typing import Any, Dict

from ..provider import secretary_tool
from .workload import WorkloadProviderBase


class CobaltProvider(WorkloadProviderBase):
    """
    Handles discovery for the Cobalt resource manager (commonly used at ALCF).
    """

    is_provider = True

    @property
    def name(self) -> str:
        return "cobalt"

    def probe(self) -> bool:
        """
        Checks for cqsub or Cobalt environment variables.
        """
        self.bin_path = shutil.which("cqsub") or shutil.which("qsub")
        return self.bin_path is not None and "COBALT_JOBID" in os.environ

    @property
    def metadata(self) -> Dict[str, Any]:
        """
        Returns Cobalt version info.
        """
        return {"version": self.run_workload_cmd(["qstat", "--version"])}

    @secretary_tool
    def get_active_jobs(self) -> str:
        """
        Retrieves all running and queued jobs in Cobalt.

        Returns:
            str: Table of jobs and their states.
        """
        return self.run_workload_cmd(["qstat", "-u", "all"])
