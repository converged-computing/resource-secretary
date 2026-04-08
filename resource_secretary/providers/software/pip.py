import json
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional

from ..provider import BaseProvider, secretary_tool


class PipProvider(BaseProvider):
    """
    Handles discovery and management of Pip-installed packages and site-package locations.
    """

    def __init__(self):
        super().__init__()
        self.bin_path: Optional[str] = None
        self.available: bool = False

    @property
    def name(self) -> str:
        return "pip"

    def probe(self) -> bool:
        """
        Locates the pip or pip3 binary.
        """
        # Prioritize pip3 in modern environments
        self.bin_path = shutil.which("pip3") or shutil.which("pip")
        self.available = self.bin_path is not None
        return self.available

    def _run(self, args: List[str]) -> str:
        if not self.bin_path:
            return "Error: Pip binary not located."
        try:
            result = subprocess.run(
                [self.bin_path] + args, capture_output=True, text=True, timeout=30
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
            "python_interpreter": sys.executable,
        }

    @secretary_tool
    def list_installations(self) -> Dict[str, Any]:
        """
        Lists the active Python prefix and site-packages locations discovered by pip.
        Returns: Dict containing the interpreter path and library locations.
        """
        # We query the underlying python to find site-package locations
        # This mirrors the "discovery" phase of environment managers
        return {
            "active_interpreter": sys.executable,
            "prefix": sys.prefix,
            "base_prefix": sys.base_prefix,
        }

    @secretary_tool
    def list_packages(self) -> List[Dict[str, Any]]:
        """
        Lists all installed packages for the current pip installation.
        Returns: List of dictionaries containing 'name' and 'version'.
        """
        raw = self._run(["list", "--format", "json"])
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, Exception):
            return []

    @secretary_tool
    def get_package_info(self, package_name: str) -> Dict[str, Any]:
        """
        Retrieves detailed metadata for a specific installed package.
        Inputs: package_name (str): The name of the package to inspect.
        Returns: Detailed metadata including summary, home-page, and requirements.
        """
        # Note: pip show doesn't have a native --json flag in older versions,
        # but the output is key-value based which is easily parseable.
        raw = self._run(["show", package_name])
        if not raw or "Error" in raw:
            return {"error": f"Package '{package_name}' not found."}

        details = {}
        for line in raw.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                details[key.strip().lower().replace("-", "_")] = value.strip()

        return details
