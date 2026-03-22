import platform
import subprocess
from typing import Any, Dict, List

import psutil

from ..provider import BaseProvider, secretary_tool


class CPUProvider(BaseProvider):
    """
    Handles discovery of CPU architecture, core counts, and instruction sets.
    """

    is_provider = True

    @property
    def name(self) -> str:
        return "cpu"

    def probe(self) -> bool:
        """
        Always active as every system has a CPU. At least... I think... :X
        """
        return True

    def get_cpu_flags(self) -> List[str]:
        """
        Retrieves CPU instruction flags (e.g., avx512, amx) from the system.
        """
        flags = []
        if platform.system() == "Linux":
            try:
                # Parse /proc/cpuinfo for flags
                with open("/proc/cpuinfo", "r") as f:
                    for line in f:
                        if line.startswith("flags") or line.startswith("Features"):
                            flags = line.split(":")[1].strip().split()
                            break
            except:
                pass
        return flags

    @property
    def metadata(self) -> Dict[str, Any]:
        """
        Returns static CPU details including model, architecture, and core counts.
        """
        return {
            "arch": platform.machine(),
            "model": platform.processor(),
            "physical_cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(logical=True),
            "flags": self.get_cpu_flags(),
        }

    @secretary_tool
    def get_current_load(self) -> Dict[str, Any]:
        """
        Retrieves the current CPU utilization percentages.

        Returns:
            Dict: Average load and per-core utilization. Use this to determine
                  if the CPU is currently over-subscribed.
        """
        return {"percent_avg": psutil.cpu_percent(interval=None), "load_avg": psutil.getloadavg()}

    @secretary_tool
    def check_instruction_support(self, feature: str) -> bool:
        """
        Checks if the CPU supports a specific instruction set.

        Inputs:
            feature (str): The flag to check for (e.g., 'avx512f', 'amx_tile').

        Returns:
            bool: True if the feature is present in CPU flags. Use this to
                  verify compatibility with highly optimized binaries.
        """
        return feature.lower() in [f.lower() for f in self.get_cpu_flags()]
