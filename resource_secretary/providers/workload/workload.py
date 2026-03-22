import shutil
import subprocess
from typing import Any, Dict, List, Optional

from ..provider import BaseProvider


class WorkloadProviderBase(BaseProvider):
    """
    Intermediate logic for HPC workload managers.
    """

    is_provider = False

    def __init__(self):
        super().__init__()
        self.bin_path: Optional[str] = None

    def run_workload_cmd(self, args: List[str]) -> str:
        """
        Executes a workload manager command directly.

        Inputs:
            args (List[str]): List of command arguments.

        Returns:
            str: The stripped stdout of the command execution.
        """
        if not self.bin_path:
            return f"Error: {self.name} binary not found."
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=15)
            return result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
        except Exception as e:
            return f"Error executing {self.name} tool: {str(e)}"
