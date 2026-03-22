import shutil
import subprocess
from typing import Any, Dict, List, Optional

from ..provider import BaseProvider


class ContainerProvider(BaseProvider):
    """
    Base class for container runtimes (Docker, Podman, Singularity, etc.).
    """

    is_provider = False

    def __init__(self):
        super().__init__()
        self.bin_path: Optional[str] = None
        self.available: bool = False

    def probe_runtime(self, binary_name: str) -> bool:
        """
        Locates the container binary and verifies it is functional.
        """
        self.bin_path = shutil.which(binary_name)
        if self.bin_path:
            try:
                # Basic execution check (version)
                result = subprocess.run(
                    [self.bin_path, "--version"], capture_output=True, text=True, timeout=5
                )
                self.available = result.returncode == 0
            except:
                self.available = False
        return self.available

    def run_container_cmd(self, args: List[str]) -> str:
        """
        Executes a container runtime command.

        Inputs:
            args (List[str]): List of command arguments.

        Returns:
            str: The stripped stdout of the command execution.
        """
        if not self.bin_path:
            return "Error: Runtime binary not found."

        try:
            result = subprocess.run(
                [self.bin_path] + args, capture_output=True, text=True, timeout=15
            )
            return result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
        except Exception as e:
            return f"Error executing command: {str(e)}"
