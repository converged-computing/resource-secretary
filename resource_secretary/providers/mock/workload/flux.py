import random
from typing import Any, Dict, List

from ...provider import dispatch_tool, secretary_tool
from ..base import MockBaseProvider


class MockFluxProvider(MockBaseProvider):
    """
    Expert Mock: Flux Framework.
    Simulates high-fidelity Python binding responses with consistent capacity math.
    """

    def __init__(self, config):
        super().__init__(config)
        self.node_count = 0
        self.idle_nodes = 0
        self.cores_per_node = 0
        self.total_cores = 0
        self.idle_cores = 0
        self._utilization = 0.0
        self.available = False

    @property
    def name(self) -> str:
        return "flux"

    def probe(self) -> bool:
        rng = self.config.get_rng("flux")

        # 1. Physical Capacity (Scale driven)
        self.node_count = self.generate("nodes", mode="scale", volatility=0.05)
        self.cores_per_node = self.generate("cpus_per_node", mode="scale", volatility=0.02)
        self.total_cores = self.node_count * self.cores_per_node

        # 2. Temporal State (Density driven)
        # Use the density target to determine utilization (the 'Pulse')
        self._utilization = max(0.0, min(0.98, rng.gauss(self.config.targets["density"], 0.1)))

        # 3. Derive Standardized Metrics
        self.idle_nodes = int(self.node_count * (1.0 - self._utilization))
        self.idle_cores = int(self.total_cores * (1.0 - self._utilization))

        self.available = True
        return True

    @property
    def metadata(self) -> Dict[str, Any]:
        return {
            "system_type": "flux",
            "total_cores": self.total_cores,
            "total_nodes": self.node_count,
            "status": "online",
        }

    @secretary_tool
    def get_resource_status(self) -> Dict[str, Any]:
        """
        flux resource list: Returns real-time availability.
        Used by the agent to verify if specific nodes/cores are free.
        """
        return {
            "free_cores": self.idle_cores,
            "total_cores": self.total_cores,
            "up_nodes": self.node_count,
            "resource_status": "online",
        }

    @secretary_tool
    def get_queue_stats(self) -> Dict[str, Any]:
        """
        Mock sched-fluxion-qmanager.stats-get.
        Provides evidence of system pressure for the agent's 'BUSY' verdict.
        """
        # Running jobs correlates with utilization
        running = int(self.node_count * self._utilization)

        # Pending jobs are higher if the system is nearly full
        pending = int(running * 1.5) if self._utilization > 0.8 else int(running * 0.2)

        return {
            "default": {
                "pending": pending,
                "running": running,
                "priority_map": "fair-share",
            }
        }

    @secretary_tool
    def get_scheduler_params(self) -> Dict[str, Any]:
        """
        Returns active configuration for the Fluxion scheduler.
        """
        return {"match-format": "v1", "policy": "easy-backfill", "traverser": "fcfs"}

    @dispatch_tool
    def submit_job(self, command: List[str], **kwargs) -> Dict[str, Any]:
        rng = self.config.get_rng("flux_dispatch")
        return {"success": True, "job_id": rng.randint(10000, 99999), "uri": "local://mock-flux"}

    def export_truth(self) -> Dict[str, Any]:
        """
        Standardized output for the SimulationAuditor.
        Allows the Scorer to verify if Agent's BUSY/READY verdict was correct.
        """
        return {
            "total_nodes": self.node_count,
            "idle_nodes": self.idle_nodes,
            "total_cores": self.total_cores,
            "cores_per_node": int(self.total_cores / self.node_count),
            "idle_cores": self.idle_cores,
            "utilization": self._utilization,
        }
