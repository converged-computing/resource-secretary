import os
import shutil
from typing import Any, Dict, Optional

from ..provider import secretary_tool
from .workload import WorkloadProviderBase


class OpenClusterSchedulerProvider(WorkloadProviderBase):
    """
    Handles discovery and status for the SGE-family schedulers.
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

    def __init__(self):
        super().__init__()
        self.qconf: Optional[str] = None
        self.qhost: Optional[str] = None

    @property
    def name(self) -> str:
        return "ocs"

    def probe(self) -> bool:
        """
        Returns True only when qsub and qconf are on PATH and SGE_ROOT is set.
        Leaves bin_path unset on PBS/Torque/Cobalt hosts so metadata cannot
        falsely advertise OCS based on a foreign qsub. Caches the qconf and
        qhost paths so the secretary tools can reference them directly.
        """
        qsub = shutil.which("qsub")
        self.qconf = shutil.which("qconf")
        self.qhost = shutil.which("qhost")
        has_sge_root = bool(os.environ.get("SGE_ROOT"))
        if qsub and self.qconf and has_sge_root:
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
                    "metadata": {"type": "manager", "flag": "-cwd"},
                    "variants": {
                        "exact": "with the -cwd flag",
                        "verbatim": "passing -cwd to qsub",
                        "descriptive": "running in the current working directory",
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
    def get_host_status(self, full: bool = False) -> str:
        """
        Retrieves execution host status (qhost): CPU, memory, load per host.

        Inputs:
            full (bool): If True, adds -F to show all resource availability
                 (complexes/consumables like memory, slots, GPUs) per host.

        Returns:
            str: Output of 'qhost'. Use this to see physical capacity and
                 current load before proposing a job.
        """
        if not self.qhost:
            return "qhost not found"
        cmd = [self.qhost]
        if full:
            cmd.append("-F")
        return self.run_workload_cmd(cmd)

    @secretary_tool
    def get_queues(self, queue: Optional[str] = None) -> str:
        """
        Lists cluster queues (qconf -sql) or shows one queue in detail (qconf -sq).

        Inputs:
            queue (str): Optional queue name. When given, returns the full queue
                 configuration (slots, hostlist, pe_list, limits) instead of the list.

        Returns:
            str: Queue names, or the detailed configuration of the requested
                 queue. Use this to find a valid queue and check its slots and
                 parallel environments before proposing a job.
        """
        if not self.qconf:
            return "qconf not found"
        cmd = [self.qconf, "-sq", queue] if queue else [self.qconf, "-sql"]
        return self.run_workload_cmd(cmd)

    @secretary_tool
    def get_cluster_config(self) -> str:
        """
        Retrieves the global cluster configuration (qconf -sconf global).

        Returns:
            str: The global SGE/OCS configuration. Use this to inspect
                 scheduler defaults, max user jobs, and other policy.
        """
        return (
            self.run_workload_cmd([self.qconf, "-sconf", "global"])
            if self.qconf
            else "qconf not found"
        )

    @secretary_tool
    def get_parallel_environments(self) -> str:
        """
        Lists configured parallel environments (qconf -spl).

        Returns:
            str: Names of parallel environments. Required to pick a valid
                 `-pe` argument for job submission.
        """
        return self.run_workload_cmd([self.qconf, "-spl"]) if self.qconf else "qconf not found"
