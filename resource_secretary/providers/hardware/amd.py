import shutil
from typing import Any, Dict

from ..provider import secretary_tool
from .gpu import GPUProviderBase


class AmdGPUProvider(GPUProviderBase):
    """
    Handles discovery and status for AMD GPU accelerators (ROCm).
    """

    is_provider = True

    @property
    def name(self) -> str:
        return "amd-gpu"

    def probe(self) -> bool:
        """
        Checks for the presence of rocm-smi.
        """
        self.bin_path = shutil.which("rocm-smi")
        return self.bin_path is not None

    @property
    def metadata(self) -> Dict[str, Any]:
        """
        Returns hardware info for AMD GPUs.
        """
        return {"vendor": "amd", "bin_path": self.bin_path}

    @secretary_tool
    def get_full_status(self) -> str:
        """
        Retrieves the complete status of all AMD GPUs via rocm-smi.

        Returns:
            str: Detailed output of temperature, load, and memory info.
        """
        return self.run_smi_cmd(["-a"])
