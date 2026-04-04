import random
from typing import Any, Dict, List, Optional

from ...provider import secretary_tool
from ..base import MockBaseProvider

CPU_MODELS = ["AMD EPYC 9654", "Intel Xeon Platinum 8480C", "AMD EPYC 7763", "Intel Xeon Gold 6338"]
GPU_CONFIGS = {
    "nvidia": ["NVIDIA H100 80GB HBM3", "NVIDIA A100-SXM4-80GB", "NVIDIA Tesla V100-SXM2"],
    "amd": ["AMD Instinct MI250X", "AMD Instinct MI210"],
}
INSTRUCTION_SETS = ["avx", "avx2", "avx512f", "avx512bw", "amx_tile", "sse4_2", "rdseed"]


class MockHardwareProvider(MockBaseProvider):
    """
    Hardware (CPU, Memory, GPU).
    Scale Anchor: Physical counts (Cores, GB, GPU counts).
    Density Anchor: Utilization and Load (How busy the node is).
    """

    def __init__(self, config):
        super().__init__(config)
        self.available = False
        self._state = {}
        self.capability_tools = {
            "compute": ["get_current_load", "get_available_memory", "check_instruction_support"],
            "environment": ["get_gpu_utilization", "get_gpu_info"],
        }

    @property
    def name(self) -> str:
        return "hardware"

    def probe(self) -> bool:
        """
        The Hardware Expert realizes the physical specs of the local node.
        """
        rng = self.config.get_rng("hardware")

        # Physical capacity (scale-driven, low volatility)
        cpu_cores = self.generate("cpus_per_node", mode="scale", volatility=0.05)
        mem_gb = self.generate("mem_per_node_gb", mode="scale", volatility=0.05)
        gpu_count = self.generate("gpus_per_node", mode="scale", volatility=0.2)

        # Busyness is density driven
        # Higher density workers are modeled as being under more system pressure
        # Returns 0.0 - 1.0
        cpu_load = self.generate_load_factor(mode="density")
        mem_usage = self.generate_load_factor(mode="density")

        # Hardware models
        cpu_model = rng.choice(CPU_MODELS)
        gpu_vendor = rng.choice(["nvidia", "amd"]) if gpu_count > 0 else "none"
        gpu_models = (
            rng.sample(GPU_CONFIGS.get(gpu_vendor, []), k=1) * gpu_count if gpu_count > 0 else []
        )

        self._state = {
            "cpu": {
                "model": cpu_model,
                "cores": cpu_cores,
                "flags": rng.sample(INSTRUCTION_SETS, k=rng.randint(3, len(INSTRUCTION_SETS))),
                "load": cpu_load,
            },
            "memory": {"total_gb": mem_gb, "usage_percent": mem_usage * 100},
            "gpu": {
                "vendor": gpu_vendor,
                "count": gpu_count,
                "models": gpu_models,
                "utilization": [rng.randint(0, 100) for _ in range(gpu_count)],
            },
        }

        self.available = True
        return True

    def generate_load_factor(self, mode="density") -> float:
        """
        Helper to generate a 0-1 load factor based on density.
        """
        rng = self.config.get_rng("hardware_load")
        density = self.config.targets.get("density")
        anchor = density if mode == "density" else 0.5
        return max(0.0, min(1.0, rng.gauss(anchor, 0.2)))

    @property
    def metadata(self) -> Dict[str, Any]:
        return {
            "cpu_model": self._state["cpu"]["model"],
            "total_cores": self._state["cpu"]["cores"],
            "total_mem_gb": self._state["memory"]["total_gb"],
            "gpu_count": self._state["gpu"]["count"],
            "gpu_vendor": self._state["gpu"]["vendor"],
        }

    @secretary_tool
    def get_current_load(self) -> Dict[str, Any]:
        """
        Retrieves current CPU utilization percentages.
        """
        load = self._state["cpu"]["load"]
        return {
            "percent_avg": round(load * 100, 1),
            "load_avg": [round(load * 2, 2), round(load * 1.8, 2), round(load * 1.5, 2)],
        }

    @secretary_tool
    def check_instruction_support(self, feature: str) -> bool:
        """
        Checks if the CPU supports a specific instruction set (e.g. avx512).
        """
        return feature.lower() in [f.lower() for f in self._state["cpu"]["flags"]]

    @secretary_tool
    def get_available_memory(self) -> Dict[str, Any]:
        """
        Retrieves real-time memory availability in GB.
        """
        total = self._state["memory"]["total_gb"]
        used_p = self._state["memory"]["usage_percent"]
        used = (used_p / 100) * total
        return {
            "total_gb": total,
            "available_gb": round(total - used, 2),
            "used_gb": round(used, 2),
            "percent": round(used_p, 1),
        }

    @secretary_tool
    def get_gpu_utilization(self) -> str:
        """
        Retrieves real-time GPU and Memory utilization.
        """
        if self._state["gpu"]["count"] == 0:
            return "No GPUs found."

        # Mimic the CSV output style of nvidia-smi/rocm-smi
        lines = []
        for i in range(self._state["gpu"]["count"]):
            util = self._state["gpu"]["utilization"][i]
            lines.append(f"{util} %, {max(0, util - 10)} %")
        return "\n".join(lines)

    @secretary_tool
    def get_gpu_info(self) -> Dict[str, Any]:
        """
        Returns details on discovered GPU hardware.
        """
        return self._state["gpu"]

    def export_truth(self) -> Dict[str, Any]:
        """
        Gold Standard for accuracy calculation.
        """
        return self._state
