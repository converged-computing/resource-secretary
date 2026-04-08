from typing import List

from ...provider import secretary_tool
from ..base import MockBaseProvider


class MockKubernetesProvider(MockBaseProvider):
    """
    Kubernetes Orchestrator.
    """

    def __init__(self, config):
        super().__init__(config)

    @property
    def name(self) -> str:
        return "kubernetes"

    def probe(self) -> bool:
        rng = self.config.get_rng("k8s")
        self.node_count = self.generate("nodes", mode="scale", volatility=0.05)

        # In K8s, we often reason about allocatable cores
        utilization = max(0.0, min(0.95, rng.gauss(self.config.targets["density"], 0.1)))
        self.total_cores = self.node_count * 64  # Assume standard high-core nodes
        self.idle_cores = int(self.total_cores * (1.0 - utilization))
        self.idle_nodes = int(self.node_count * (1.0 - utilization))

        # Density determines namespace count
        ns_count = max(2, int(10 * self.config.targets["density"]))
        self._namespaces = [f"project-{rng.randint(100, 999)}" for _ in range(ns_count)]
        self._namespaces.extend(["default", "kube-system"])
        self.available = True
        return True

    @secretary_tool
    def list_namespaces(self) -> List[str]:
        """
        Mock kubectl get namespaces.
        """
        return self._namespaces

    @secretary_tool
    def get_resource_capacity(self) -> str:
        """
        Mock kubectl get nodes with custom columns.
        """
        header = f"{'NAME':<20} {'STATUS':<10} {'CPU':<5} {'MEMORY':<10}"
        lines = [header]
        for i in range(min(self.node_count, 10)):  # Truncate for context safety
            lines.append(f"node-{i:03d}             Ready      64    256Gi")
        if self.node_count > 10:
            lines.append(f"... and {self.node_count - 10} more nodes.")
        return "\n".join(lines)

    def export_truth(self):
        return {
            "cores_per_node": int(self.total_cores / self.node_count),
            "total_nodes": self.node_count,
            "idle_nodes": self.idle_nodes,
            "namespaces": self._namespaces,
            "total_cores": self.total_cores,
            "idle_cores": self.idle_cores,
        }
