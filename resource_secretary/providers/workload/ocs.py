import os
import shutil
from typing import Any, Dict, Optional

from ..provider import secretary_tool
from .workload import WorkloadProviderBase


class OpenClusterSchedulerProvider(WorkloadProviderBase):
    """
    Handles discovery and status for the SGE-family schedulers:
    Open Cluster Scheduler (OCS) and Gridware Cluster Scheduler (GCS),
    both descendants of Sun Grid Engine. They share the same CLI surface
    (qsub, qstat, qhost, qconf, qacct) and the same SGE_ROOT/SGE_CELL
    environment contract, so one provider covers both.

    Probe disambiguates from PBS/Torque/Cobalt (which also ship `qsub`) by
    requiring `qconf` on PATH and the SGE_ROOT environment variable to be set.
    OCS/GCS use parallel environments (-pe NAME SLOTS) as the unit of work;
    the LAMMPS prompt matrix expects a `pe` parameter (supplied via
    --params pe=mpi).
    """

    is_provider = True

    @property
    def name(self) -> str:
        return "ocs"

    def probe(self) -> bool:
        """
        Returns True only when qsub and qconf are on PATH and SGE_ROOT is set.
        Leaves bin_path unset on PBS/Torque/Cobalt hosts so metadata cannot
        falsely advertise OCS based on a foreign qsub.
        """
        qsub = shutil.which("qsub")
        has_qconf = shutil.which("qconf") is not None
        has_sge_root = bool(os.environ.get("SGE_ROOT"))
        if qsub and has_qconf and has_sge_root:
            self.bin_path = qsub
            return True
        self.bin_path = None
        return False

    @property
    def metadata(self) -> Dict[str, Any]:
        """
        Returns OCS/GCS installation summary.
        """
        if not self.bin_path:
            return {"installed": False}
        return {
            "system_type": "ocs",
            "sge_root": os.environ.get("SGE_ROOT"),
            "sge_cell": os.environ.get("SGE_CELL", "default"),
            "status": "online",
        }

    def get_prompt_vocabulary(self) -> Dict[str, Any]:
        """
        Returns OCS-specific templates for the prompt generator.
        """
        return {
            "manager": {
                "exact": "qsub -b y",
                "verbatim": "using qsub -b y",
                "descriptive": "using Open Cluster Scheduler (qsub)",
                "agnostic": "submit {app}",
            },
            "resources": {
                "exact": "-pe {pe} {tasks}",
                "verbatim": "with -pe {pe} {tasks}",
                "descriptive": "execute {app} on {tasks} slots in the {pe} parallel environment",
                "discovery": "using available slots in the default parallel environment",
            },
            "modifiers": {
                "cwd": {
                    "type": "manager",
                    "flag": "-cwd",
                    "variants": {
                        "exact": "with the -cwd flag",
                        "verbatim": "passing -cwd to qsub",
                        "descriptive": "running in the current working directory",
                    },
                },
                "merge_output": {
                    "type": "manager",
                    "flag": "-j y",
                    "variants": {
                        "exact": "with the -j y flag",
                        "verbatim": "passing -j y to qsub",
                        "descriptive": "merging stderr into stdout",
                    },
                },
            },
            "syntax": {"run_cmd": "qsub -b y", "resource_flags": "-pe {pe} {tasks}"},
        }

    @secretary_tool
    def get_queue_status(self, user: Optional[str] = None) -> str:
        """
        Retrieves the current OCS job queue (qstat).

        Inputs:
            user (str): Optional username filter (-u).

        Returns:
            str: A list of running and pending jobs. Use this to estimate
                 wait times and current cluster pressure.
        """
        cmd = ["qstat"]
        if user:
            cmd += ["-u", user]
        return self.run_workload_cmd(cmd)

    @secretary_tool
    def get_host_status(self) -> str:
        """
        Retrieves execution host status (qhost): CPU, memory, load per host.

        Returns:
            str: Output of 'qhost'. Use this to see physical capacity and
                 current load before proposing a job.
        """
        tool = shutil.which("qhost")
        return self.run_workload_cmd([tool]) if tool else "qhost not found"

    @secretary_tool
    def get_cluster_config(self) -> str:
        """
        Retrieves the global cluster configuration (qconf -sconf global).

        Returns:
            str: The global SGE/OCS configuration. Use this to inspect
                 scheduler defaults, max user jobs, and other policy.
        """
        tool = shutil.which("qconf")
        return self.run_workload_cmd([tool, "-sconf", "global"]) if tool else "qconf not found"

    @secretary_tool
    def get_parallel_environments(self) -> str:
        """
        Lists configured parallel environments (qconf -spl).

        Returns:
            str: Names of parallel environments. Required to pick a valid
                 `-pe` argument for job submission.
        """
        tool = shutil.which("qconf")
        return self.run_workload_cmd([tool, "-spl"]) if tool else "qconf not found"
