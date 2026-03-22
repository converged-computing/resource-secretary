import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..provider import BaseProvider, secretary_tool


class SpackProvider(BaseProvider):
    """
    The Spack provider handles software environment discovery and package lookups.
    It ensures that all tool calls are executed within a sourced Spack environment.
    """

    def __init__(self):
        super().__init__()
        self.root: Optional[Path] = None
        self.setup_script: Optional[Path] = None
        self.version: str = "unknown"
        self.arch: str = "unknown"
        self.available: bool = False

    @property
    def name(self) -> str:
        return "spack"

    def probe(self) -> bool:
        """
        Locate spack through SPACK_ROOT or fall back to the system PATH.

        Returns:
            bool: True if the spack setup script is found and the provider is active.
        """
        root_env = os.environ.get("SPACK_ROOT")
        if root_env:
            self.root = Path(root_env)

        if not self.root:
            spack_bin = shutil.which("spack")
            if spack_bin:
                self.root = Path(spack_bin).resolve().parent.parent

        if self.root and self.root.exists():
            # The shell setup script is the 'Source of Truth' for Spack environment sourcing
            setup = self.root / "share" / "spack" / "setup-env.sh"
            if setup.exists():
                self.setup_script = setup
                self.available = True
                self._detect_metadata()

        return self.available

    def run_spack(self, cmd: str) -> str:
        """
        Helper to run a command within the sourced Spack environment.
        Ensures aliases and functions are available in the subshell.

        Inputs:
            cmd (str): The raw spack command string to execute.

        Returns:
            str: The stripped stdout of the command execution.
        """
        if not self.setup_script:
            return ""

        full_cmd = f". {self.setup_script} && {cmd}"
        try:
            result = subprocess.run(
                ["bash", "-c", full_cmd], capture_output=True, text=True, timeout=15
            )
            return result.stdout.strip()
        except Exception as e:
            return f"Error executing spack command: {str(e)}"

    def _detect_metadata(self):
        """
        Initializes version and architecture metadata.
        """
        self.version = self.run_spack("spack --version")
        self.arch = self.run_spack("spack arch")

    @property
    def metadata(self) -> Dict[str, Any]:
        """
        Returns the static state of the Spack installation.

        Returns:
            Dict: Includes 'root' path, 'version' string, 'target_arch', and
                  a list of 'compilers' available to Spack.
        """
        if not self.available:
            return {"installed": False}

        return {
            "root": str(self.root),
            "version": self.version,
            "target_arch": self.arch,
            "compilers": self.run_spack("spack compiler list").split(),
        }

    # Secretary Tools

    @secretary_tool
    def find_package(self, query: str) -> Any:
        """
        Searches the local cluster for installed Spack packages matching the query.

        Inputs:
            query (str): The package name or partial spec to search for (e.g., 'lammps' or 'lammps+kokkos').

        Returns:
            List[Dict] or Dict: A list of JSON objects representing installed matching packages,
                                including their specific versions, build variants, and dependencies.
                                Returns a message dictionary if no matches are found.
        """
        raw_json = self.run_spack(f"spack find --json {query}")
        try:
            return json.loads(raw_json)
        except:
            return {"message": f"No installed packages found matching: {query}"}

    @secretary_tool
    def get_package_info(self, name: str) -> str:
        """
        Retrieves the detailed 'spack info' for a specific package name.

        Inputs:
            name (str): The exact name of the package (e.g., 'lammps').

        Returns:
            str: A human-readable description of the package including all available
                 versions, possible build variants, and required dependencies.
        """
        return self.run_spack(f"spack info {name}")
