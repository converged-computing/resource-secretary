import shutil
from typing import Any, Dict

from ..provider import secretary_tool
from .gpu import GPUProviderBase


class NvidiaGPUProvider(GPUProviderBase):
    """
    Handles discovery and status for NVIDIA GPU accelerators.
    """

    is_provider = True

    @property
    def name(self) -> str:
        return "nvidia-gpu"

    def probe(self) -> bool:
        """
        Checks for the presence of nvidia-smi.
        """
        self.bin_path = shutil.which("nvidia-smi")
        return self.bin_path is not None

    @property
    def metadata(self) -> Dict[str, Any]:
        """
        Returns the GPU count and model names discovered via nvidia-smi.
        """
        models = self.run_smi_cmd(["--query-gpu=gpu_name", "--format=csv,noheader"]).splitlines()
        return {
            "vendor": "nvidia",
            "count": len(models),
            "models": [m.strip() for m in models],
            "driver_version": self.run_smi_cmd(
                ["--query-gpu=driver_version", "--format=csv,noheader"]
            ).splitlines()[0],
        }

    @secretary_tool
    def get_utilization(self) -> str:
        """
        Retrieves real-time GPU and Memory utilization.

        Returns:
            str: CSV output of utilization percentages. Use this to see
                 if GPUs are currently busy or idle.
        """
        return self.run_smi_cmd(
            ["--query-gpu=utilization.gpu,utilization.memory", "--format=csv,noheader"]
        )

    @secretary_tool
    def get_memory_info(self) -> str:
        """
        Retrieves total, used, and free VRAM for all GPUs.

        Returns:
            str: CSV output of memory statistics. Use this to verify if
                 a job's data will fit into the available GPU memory.
        """
        return self.run_smi_cmd(
            ["--query-gpu=memory.total,memory.used,memory.free", "--format=csv,noheader"]
        )
