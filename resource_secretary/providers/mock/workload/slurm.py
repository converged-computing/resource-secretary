import random
from typing import Any, Dict, List, Optional

from ...provider import secretary_tool
from ..base import MockBaseProvider


class MockSlurmProvider(MockBaseProvider):
    def __init__(self, config):
        super().__init__(config)
        self.node_count = 0
        self.idle_nodes = 0
        self.busy_nodes = 0
        self.cores_per_node = 0
        self.partitions = []
        self._jobs = []
        self.available = False

    @property
    def name(self) -> str:
        return "slurm"

    def probe(self) -> bool:
        rng = self.config.get_rng("slurm")

        # 1. Physical Capacity
        self.node_count = self.generate("nodes", mode="scale", volatility=0.05)
        self.cores_per_node = self.generate("cpus_per_node", mode="scale")
        self.total_cores = self.node_count * self.cores_per_node

        # 2. Partition Variety (Density)
        partition_count = self.generate("partitions", mode="density", volatility=0.1)
        pool = ["compute", "gpu", "debug", "highmem", "long", "viz"]
        self.partitions = rng.sample(pool, k=min(partition_count, len(pool)))

        # 3. Temporal State (The Pulse)
        # Higher density target = higher utilization (busier system)
        utilization = max(0.0, min(0.98, rng.gauss(self.config.targets["density"], 0.1)))

        self.idle_nodes = int(self.node_count * (1.0 - utilization))
        self.busy_nodes = self.node_count - self.idle_nodes
        self.idle_cores = self.idle_nodes * self.cores_per_node

        # 4. Generate the Job Queue based on busy nodes
        self._set_jobs(rng, self.busy_nodes)

        self.available = True
        return True

    def _set_jobs(self, rng, busy_nodes):
        """
        Generates faux jobs for busy nodes.
        """
        self._jobs = []
        nodes_remaining = busy_nodes
        job_id = 1000

        while nodes_remaining > 0:
            # Each job takes 1 to 10% of the cluster
            job_size = rng.randint(1, max(1, self.node_count // 10))
            job_size = min(job_size, nodes_remaining)

            self._jobs.append(
                {
                    "id": job_id,
                    "user": rng.choice(["root", "user1", "researcher", "student"]),
                    "state": "RUNNING",
                    "time": f"{rng.randint(0, 23)}:{rng.randint(10, 59)}",
                    "nodes": job_size,
                }
            )
            nodes_remaining -= job_size
            job_id += 1

        # Add some PENDING jobs for 'Queue Pressure'
        num_pending = int(self.busy_nodes * 0.2)
        for i in range(num_pending):
            self._jobs.append(
                {
                    "id": job_id + i,
                    "user": rng.choice(["user1", "researcher"]),
                    "state": "PENDING",
                    "time": "0:00",
                    "nodes": rng.randint(1, 4),
                }
            )

    @secretary_tool
    def get_resource_info(self) -> str:
        """
        sinfo -N -l: Slurm output for node states.
        """
        header = "NODELIST   NODES   PARTITION       STATE CPUS    MEMORY    FEATURES REASON"
        lines = [header]
        # Summarize for the agent
        lines.append(
            f"node[001-{self.idle_nodes:03d}]  {self.idle_nodes}   {self.partitions[0]}  idle  {self.cores_per_node}  256000  none (null)"
        )
        if self.busy_nodes > 0:
            lines.append(
                f"node[{self.idle_nodes+1:03d}-{self.node_count:03d}]  {self.busy_nodes}   {self.partitions[0]}  alloc {self.cores_per_node}  256000  none (null)"
            )
        return "\n".join(lines)

    @secretary_tool
    def get_queue_status(self, user: Optional[str] = None) -> str:
        """
        squeue: list of jobs.
        """
        header = (
            f"{'JOBID':<8} {'PARTITION':<12} {'USER':<10} {'STATE':<10} {'TIME':<10} {'NODES':<5}"
        )
        lines = [header]
        filtered = [j for j in self._jobs if not user or j["user"] == user]
        for j in filtered[:50]:
            lines.append(
                f"{j['id']:<8} {self.partitions[0]:<12} {j['user']:<10} {j['state']:<10} {j['time']:<10} {j['nodes']:<5}"
            )
        return "\n".join(lines)

    def export_truth(self):
        """
        State of truth of cluster.
        """
        return {
            "total_nodes": self.node_count,
            "idle_nodes": self.idle_nodes,
            "busy_nodes": self.busy_nodes,
            "cores_per_node": int(self.total_cores / self.node_count),
            "total_cores": self.total_cores,
            "idle_cores": self.idle_cores,
            "job_count": len(self._jobs),
            "partitions": self.partitions,
        }
