import shutil
import subprocess
from typing import Any, Dict

from ..provider import BaseProvider, secretary_tool


class OpenMPIProvider(BaseProvider):
    """
    Specialized provider for OpenMPI implementations.
    """

    def __init__(self):
        super().__init__()
        self.available = False

    @property
    def name(self) -> str:
        return "openmpi"

    def probe(self) -> bool:
        """Checks for the presence of ompi_info."""
        self.available = shutil.which("ompi_info") is not None
        return self.available

    def run_ompi_info(self, args: list) -> str:
        """Executes ompi_info to get implementation details."""
        try:
            res = subprocess.run(["ompi_info"] + args, capture_output=True, text=True, timeout=10)
            return res.stdout.strip()
        except Exception as e:
            return str(e)

    @property
    def metadata(self) -> Dict[str, Any]:
        """Returns the OpenMPI version and configuration summary."""
        return {
            "version": (
                self.run_ompi_info(["--version", "--parsable"]).splitlines()[0]
                if self.available
                else "unknown"
            ),
            "launcher": shutil.which("mpirun"),
        }

    @secretary_tool
    def get_ompi_config(self) -> str:
        """
        Retrieves detailed compilation and network support info for OpenMPI.

        Returns:
            str: Full output of ompi_info.
        """
        return self.run_ompi_info([])
