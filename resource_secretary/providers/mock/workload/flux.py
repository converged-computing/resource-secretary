import random
from typing import Any, Dict, List, Optional

from ...provider import dispatch_tool, secretary_tool
from ..base import MockBaseProvider


class MockFluxProvider(MockBaseProvider):
    """
    Expert Mock: Flux Framework.
    Simulates high-fidelity Python binding responses.
    """

    def __init__(self, config):
        super().__init__(config)
        self.node_count = 0
        self.cores_per_node = 0
        self._utilization = 0.0
        self.available = False

    @property
    def name(self) -> str:
        return "flux"

    def probe(self) -> bool:
        rng = self.config.get_rng("flux")

        self.node_count = self.generate("nodes", mode="scale", volatility=0.05)
        self.cores_per_node = self.generate("cpus_per_node", mode="scale", volatility=0.02)
        self._utilization = max(0.0, min(0.98, rng.gauss(self.config.targets["density"], 0.1)))
        self.available = True
        return True

    @property
    def metadata(self) -> Dict[str, Any]:
        return {
            "system_type": "flux",
            "total_cores": self.node_count * self.cores_per_node,
            "total_nodes": self.node_count,
            "status": "online",
        }

    @secretary_tool
    def get_resource_status(self) -> Dict[str, Any]:
        """
        flux resource list: Returns real-time availability.
        """
        total_cores = self.node_count * self.cores_per_node
        free_cores = int(total_cores * (1.0 - self._utilization))

        return {
            "free_cores": free_cores,
            "total_cores": total_cores,
            "up_nodes": self.node_count,
        }

    @secretary_tool
    def get_queue_stats(self) -> Dict[str, Any]:
        """
        Mock sched-fluxion-qmanager.stats-get.
        """
        return {
            "default": {
                "pending": int(self.node_count * self._utilization * 2),
                "running": int(self.node_count * self._utilization),
                "priority_map": "fair-share",
            }
        }

    @secretary_tool
    def get_scheduler_params(self) -> Dict[str, Any]:
        return {"match-format": "v1", "policy": "easy-backfill", "traverser": "depth-first"}

    @dispatch_tool
    def submit_job(self, command: List[str], **kwargs) -> Dict[str, Any]:
        """
        Mock job submission.
        """
        rng = self.config.get_rng("flux_dispatch")
        return {"success": True, "job_id": rng.randint(10000, 99999), "uri": "local://mock-flux"}

    def export_truth(self):
        return {
            "total_nodes": self.node_count,
            "cores_per_node": self.cores_per_node,
            "utilization": self._utilization,
        }
