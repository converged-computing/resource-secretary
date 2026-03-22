import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional

from ..provider import BaseProvider


class NetworkProvider(BaseProvider):
    """
    Intermediate logic for network fabric discovery.
    Explicitly not a provider as it serves as a base for specific fabrics.
    """

    is_provider = False

    def __init__(self):
        super().__init__()
        self.available = False

    def run_network_cmd(self, args: List[str]) -> str:
        """
        Executes a network utility command directly.

        Inputs:
            args (List[str]): List of command arguments.

        Returns:
            str: The stripped stdout of the command execution.
        """
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=10)
            return result.stdout.strip()
        except Exception as e:
            return f"Error executing network tool: {str(e)}"

    def check_path_exists(self, path: str) -> bool:
        """
        Verifies if a specific system path exists (e.g. in /sys/class).

        Inputs:
            path (str): The directory or file path to check.

        Returns:
            bool: True if the path exists on the filesystem.
        """
        return os.path.exists(path)
