import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional

from ..provider import BaseProvider, secretary_tool


class SlurmProvider(BaseProvider):
    """
    The Slurm provider manages interaction with the Slurm Workload Manager.
    It provides manifest data (partitions) and agent tools (sinfo/squeue).
    """

    def __init__(self):
        super().__init__()
        self.available: bool = False
        self.bin_path: Optional[str] = None

    @property
    def name(self) -> str:
        return "slurm"

    def probe(self) -> bool:
        """
        Locates the Slurm binaries (sbatch/sinfo) and verifies availability.

        Returns:
            bool: True if Slurm binaries are found in the system PATH.
        """
        self.bin_path = shutil.which("sbatch")
        self.available = self.bin_path is not None
        return self.available

    def run_slurm_cmd(self, cmd: List[str]) -> str:
        """
        Executes a Slurm CLI tool directly as a subprocess.

        Inputs:
            cmd (List[str]): List of command arguments (e.g., ['sinfo', '-h']).

        Returns:
            str: The stripped stdout of the command execution.
        """
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return result.stdout.strip()
        except Exception as e:
            return f"Error executing slurm command: {str(e)}"

    @property
    def metadata(self) -> Dict[str, Any]:
        """
        Returns partitions and total capacity.

        Returns:
            Dict: Includes 'partitions' list, 'has_srun' boolean, and
                  system type 'slurm'.
        """
        if not self.available:
            return {"installed": False}

        # Get partition list: sinfo -h -o "%P"
        partitions = self.run_slurm_cmd(["sinfo", "-h", "-o", "%P"]).split()

        return {
            "system_type": "slurm",
            "partitions": partitions,
            "has_srun": shutil.which("srun") is not None,
            "status": "online",
        }

    # Secretary Tools

    @secretary_tool
    def get_resource_info(self) -> str:
        """
        Retrieves a summary of node states and core availability across partitions.

        Returns:
            str: The output of 'sinfo', showing nodes that are idle, allocated, or down.
                 Use this to see if the cluster is physically empty or full.
        """
        return self.run_slurm_cmd(["sinfo", "-N", "-l"])

    @secretary_tool
    def get_queue_status(self, user: Optional[str] = None) -> str:
        """
        Retrieves the current job queue (squeue).

        Inputs:
            user (str): Optional username to filter the queue (e.g., 'root').

        Returns:
            str: A list of running and pending jobs. Use this to estimate
                 wait times and identify current cluster pressure.
        """
        cmd = ["squeue"]
        if user:
            cmd += ["-u", user]
        return self.run_slurm_cmd(cmd)
