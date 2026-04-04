import random
from typing import Any, Dict, List, Optional

from ...provider import secretary_tool
from ..base import MockBaseProvider


class MockMachineProvider(MockBaseProvider):
    """
    Expert Mock: Local Machine (Direct Execution).
    Acts as a Workload Manager for standalone systems.
    """

    def __init__(self, config):
        super().__init__(config)
        self.node_count = 1  # Always 1 for standalone
        self.total_cores = 0
        self.idle_cores = 0
        self.available = False

    @property
    def name(self) -> str:
        return "machine"

    def probe(self) -> bool:
        rng = self.config.get_rng("machine")

        # Standalone machines usually have 4 to 64 cores
        self.total_cores = self.generate("cpus_per_node", mode="scale", volatility=0.05)

        # 2. Temporal State (The Pulse)
        # High density = high load = fewer 'idle' cores
        load_factor = max(0.0, min(0.98, rng.gauss(self.config.targets["density"], 0.1)))

        self.idle_cores = int(self.total_cores * (1.0 - load_factor))
        self.idle_nodes = 1 if load_factor < 0.8 else 0  # System is 'busy' if load > 80%
        self.available = True
        return True

    @property
    def metadata(self) -> Dict[str, Any]:
        return {"system_type": "standalone", "total_cores": self.total_cores, "status": "online"}

    @secretary_tool
    def get_resource_info(self) -> str:
        """
        uptime and nproc summary.
        Returns current load and core availability.
        """
        load = round(self.config.density_target * 4, 2)
        return (
            f"System: {self.config.system_name}\n"
            f"Cores: {self.total_cores} total, {self.idle_cores} currently idle\n"
            f"Load Average: {load}, {load-0.1}, {load-0.2}\n"
            f"Status: {'Available' if self.idle_nodes > 0 else 'Heavily Loaded'}"
        )

    @secretary_tool
    def get_process_status(self) -> List[Dict[str, Any]]:
        """
        ps or top output.
        Returns a list of high-resource processes.
        """
        rng = self.config.get_rng("ps")
        procs = []
        if self.idle_nodes == 0:
            procs.append(
                {
                    "pid": 1234,
                    "user": "researcher",
                    "cpu_pct": 95.0,
                    "command": "python heavy_sim.py",
                }
            )
        return procs

    def export_truth(self) -> Dict[str, Any]:
        return {
            "total_nodes": self.node_count,
            "idle_nodes": self.idle_nodes,
            "total_cores": self.total_cores,
            "cores_per_node": self.total_cores,
            "idle_cores": self.idle_cores,
        }
