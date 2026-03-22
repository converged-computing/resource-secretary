import os
import shutil
import subprocess
from typing import Any, Dict

from ..provider import BaseProvider, secretary_tool


class SpectrumMPIProvider(BaseProvider):
    """
    Specialized provider for IBM Spectrum MPI.
    """

    def __init__(self):
        super().__init__()
        self.available = False

    @property
    def name(self) -> str:
        return "spectrum-mpi"

    def probe(self) -> bool:
        """
        Checks for Spectrum MPI specific signatures like smpi_info or MPI_ROOT.
        """
        has_bin = shutil.which("smpi_info") is not None
        has_env = "MPI_ROOT" in os.environ and "spectrum" in os.environ.get("MPI_ROOT", "").lower()
        self.available = has_bin or has_env
        return self.available

    @property
    def metadata(self) -> Dict[str, Any]:
        """
        Returns Spectrum MPI version and path info.
        """
        return {
            "root": os.environ.get("MPI_ROOT", "unknown"),
            "has_jsrun": shutil.which("jsrun") is not None,
        }

    @secretary_tool
    def get_smpi_details(self) -> str:
        """
        Retrieves specific build and interconnect support info for Spectrum MPI.

        Returns:
            str: Output from smpi_info.
        """
        if shutil.which("smpi_info"):
            try:
                return subprocess.check_output(["smpi_info"], text=True).strip()
            except Exception as e:
                return str(e)
        return "smpi_info binary not found."
