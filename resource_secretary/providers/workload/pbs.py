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
        Checks for qsub and ensures it is not a Cobalt or SGE/OCS/GCS
        environment.

        TODO: this probe is over-permissive. Any qsub on PATH passes today,
        which would false-positive on OCS/GCS hosts where qsub belongs to the
        SGE family. As a workaround we exclude SGE_ROOT and COBALT_JOBID
        environments. A proper fix should require a PBS-specific signal
        (e.g. PBS_SERVER env, presence of pbs_server / pbsnodes binaries,
        or a successful 'qstat --version' identifying PBS).
        """
        self.bin_path = shutil.which("qsub")
        if not self.bin_path:
            return False
        if "COBALT_JOBID" in os.environ:
            return False
        if os.environ.get("SGE_ROOT"):
            return False
        return True

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
