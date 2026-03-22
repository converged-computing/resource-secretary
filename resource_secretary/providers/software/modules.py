import os
import subprocess
from typing import Any, Dict, List, Optional

from ..provider import BaseProvider, secretary_tool


class EnvironmentModulesProvider(BaseProvider):
    """
    Handles Environment Modules (Lmod or TCL).
    Since 'module' is a shell function, this provider uses login shells for discovery.
    """

    def __init__(self):
        super().__init__()
        self.available: bool = False
        self.module_type: str = "unknown"

    @property
    def name(self) -> str:
        return "modules"

    def probe(self) -> bool:
        """
        Probes for module system fingerprints (LMOD_CMD or MODULEPATH).

        Returns:
            bool: True if a module system environment is detected.
        """
        if "LMOD_CMD" in os.environ:
            self.module_type = "lmod"
            self.available = True
        elif "MODULEPATH" in os.environ or "MODULESHOME" in os.environ:
            self.module_type = "tcl"
            self.available = True

        return self.available

    def run_module_cmd(self, cmd: str) -> str:
        """
        Executes a command in a login shell to ensure the 'module' function is defined.

        Inputs:
            cmd (str): The arguments to pass to the 'module' command (e.g., 'avail').

        Returns:
            str: The combined stdout/stderr of the 'module' command execution.
        """
        # We redirect stderr because many module systems print avail/list info to stderr
        full_cmd = f"bash -l -c 'module {cmd} 2>&1'"
        try:
            result = subprocess.run(
                full_cmd, shell=True, capture_output=True, text=True, timeout=15
            )
            return result.stdout.strip()
        except Exception as e:
            return f"Error executing module command: {str(e)}"

    @property
    def metadata(self) -> Dict[str, Any]:
        """
        Returns the type of module system and current MODULEPATH.

        Returns:
            Dict: Includes 'module_system_type', 'modulepath' list, and 'lmod_version'.
        """
        if not self.available:
            return {"installed": False}

        return {
            "module_system_type": self.module_type,
            "modulepath": os.environ.get("MODULEPATH", "").split(":"),
            "lmod_version": os.environ.get("LMOD_VERSION", "N/A"),
        }

    # Secretary Tools

    @secretary_tool
    def list_available_modules(self, query: str = "") -> str:
        """
        Searches for available software modules on the cluster.

        Inputs:
            query (str): Optional search string to filter the modules (e.g., 'lammps').

        Returns:
            str: A list of matching module names and versions. Use this to check
                 if specific software packages are available to be loaded.
        """
        return self.run_module_cmd(f"avail {query}")

    @secretary_tool
    def get_module_details(self, module_name: str) -> str:
        """
        Retrieves detailed information for a specific module.

        Inputs:
            module_name (str): The full module name/version (e.g., 'gcc/12.1.0').

        Returns:
            str: The output of 'module show' or 'module spider'. Use this to
                 verify dependencies or environment variables set by the module.
        """
        verb = "spider" if self.module_type == "lmod" else "show"
        return self.run_module_cmd(f"{verb} {module_name}")
