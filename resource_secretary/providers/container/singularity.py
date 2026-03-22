import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional

from ..provider import BaseProvider, secretary_tool


class SingularityProvider(BaseProvider):
    """
    Provider for the Singularity container runtime.
    Also serves as the base for Apptainer due to shared CLI syntax.
    """

    def __init__(self):
        super().__init__()
        self.bin_path: Optional[str] = None
        self.available: bool = False

    @property
    def name(self) -> str:
        return "singularity"

    def probe(self) -> bool:
        """
        Locates the singularity binary and verifies it is functional.
        """
        self.bin_path = shutil.which("singularity")
        if self.bin_path:
            try:
                result = subprocess.run(
                    [self.bin_path, "version"], capture_output=True, text=True, timeout=5
                )
                self.available = result.returncode == 0
            except Exception:
                self.available = False
        return self.available

    def run_command(self, args: List[str]) -> str:
        """
        Executes a command using the discovered runtime binary.
        """
        if not self.bin_path:
            return f"Error: {self.name} binary not found."

        try:
            result = subprocess.run(
                [self.bin_path] + args, capture_output=True, text=True, timeout=15
            )
            return result.stdout.strip()
        except Exception as e:
            return f"Error executing {self.name}: {str(e)}"

    @property
    def metadata(self) -> Dict[str, Any]:
        """
        Returns the Singularity version and cache location.
        """
        return {
            "runtime": "singularity",
            "version": self.run_command(["version"]),
            "cache_dir": os.environ.get("SINGULARITY_CACHEDIR", "default"),
        }

    @secretary_tool
    def list_cache(self) -> str:
        """
        Lists images currently stored in the local container cache.

        Returns:
            str: A list of cached images (SIF files). Use this to check
                 if a containerized app is already available for immediate use.
        """
        return self.run_command(["cache", "list", "-v"])


class ApptainerProvider(SingularityProvider):
    """
    Provider for the Apptainer container runtime.
    Inherits CLI execution and tool logic from Singularity.
    """

    @property
    def name(self) -> str:
        return "apptainer"

    def probe(self) -> bool:
        """
        Locates the apptainer binary specifically.
        """
        self.bin_path = shutil.which("apptainer")
        if self.bin_path:
            try:
                result = subprocess.run(
                    [self.bin_path, "version"], capture_output=True, text=True, timeout=5
                )
                self.available = result.returncode == 0
            except Exception:
                self.available = False
        return self.available

    @property
    def metadata(self) -> Dict[str, Any]:
        """
        Returns the Apptainer version and cache location.
        """
        return {
            "runtime": "apptainer",
            "version": self.run_command(["version"]),
            "cache_dir": os.environ.get("APPTAINER_CACHEDIR", "default"),
        }
