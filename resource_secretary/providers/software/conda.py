import json
import shutil
import subprocess
from typing import Any, Dict, List, Optional

from ..provider import BaseProvider, secretary_tool


class CondaProvider(BaseProvider):
    """
    Handles discovery and management of Conda/Mamba environments.
    """

    def __init__(self):
        super().__init__()
        self.bin_path: Optional[str] = None
        self.available: bool = False

    @property
    def name(self) -> str:
        return "conda"

    def probe(self) -> bool:
        """Locates the conda or mamba binary."""
        self.bin_path = shutil.which("mamba") or shutil.which("conda")
        self.available = self.bin_path is not None
        return self.available

    def _run(self, args: List[str]) -> str:
        try:
            result = subprocess.run(
                [self.bin_path] + args, capture_output=True, text=True, timeout=20
            )
            return result.stdout.strip()
        except Exception as e:
            return f"Error: {str(e)}"

    @property
    def metadata(self) -> Dict[str, Any]:
        if not self.available:
            return {"installed": False}
        return {
            "bin": self.bin_path,
            "version": self._run(["--version"]),
        }

    @secretary_tool
    def list_environments(self) -> Dict[str, Any]:
        """
        Lists all discovered Conda environments on the system.
        Returns: Dict containing a list of environment paths and names.
        """
        raw = self._run(["env", "list", "--json"])
        try:
            return json.loads(raw)
        except:
            return {"error": "Failed to parse conda env list"}

    @secretary_tool
    def list_packages(self, env_name: str) -> List[Dict[str, Any]]:
        """
        Lists installed packages in a specific environment.
        Inputs: env_name (str): The name or path of the environment.
        """
        raw = self._run(["list", "-n", env_name, "--json"])
        try:
            return json.loads(raw)
        except:
            return []
