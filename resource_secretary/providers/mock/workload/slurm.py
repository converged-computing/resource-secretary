import random
from typing import Any, Dict, List, Optional

from ...provider import secretary_tool
from ..base import MockBaseProvider


class MockSlurmProvider(MockBaseProvider):
    """
    Slurm Workload Manager.
    Scale Anchor: Node counts.
    Density Anchor: Partition variety and Queue pressure.
    """

    def __init__(self, config):
        super().__init__(config)
        self.node_count = 0
        self.partitions = []
        self._jobs = []
        self.available = False

    @property
    def name(self) -> str:
        return "slurm"

    def probe(self) -> bool:
        rng = self.config.get_rng("slurm")

        # Nodes and partitions
        self.node_count = self.generate("nodes", mode="scale", volatility=0.05)
        partition_count = self.generate("partitions", mode="density", volatility=0.1)
        pool = ["compute", "gpu", "debug", "highmem", "long", "viz"]
        self.partitions = rng.sample(pool, k=min(partition_count, len(pool)))

        # internal job state for squeue (sqweeee!)
        num_jobs = int(self.node_count * self.config.targets["density"] * 0.5)
        self._jobs = []
        for i in range(num_jobs):
            self._jobs.append(
                {
                    "id": 1000 + i,
                    "user": rng.choice(["root", "user1", "researcher", "student"]),
                    "state": rng.choice(["RUNNING", "PENDING", "PENDING"]),
                    "time": f"{rng.randint(0, 23)}:{rng.randint(10, 59)}",
                    "nodes": rng.randint(1, max(1, self.node_count // 10)),
                }
            )

        self.available = True
        return True

    @property
    def metadata(self) -> Dict[str, Any]:
        return {
            "system_type": "slurm",
            "partitions": self.partitions,
            "has_srun": True,
            "total_nodes": self.node_count,
        }

    @secretary_tool
    def get_resource_info(self) -> str:
        """
        sinfo -N -l: Returns node states and core availability.
        """
        # We simulate the header and row-based output of Slurm
        header = "NODELIST   NODES   PARTITION       STATE CPUS    S:C:T MEMORY TMP_DISK WEIGHT FEATURES REASON"
        lines = [header]

        # We group nodes into chunks to keep the output readable but realistic
        chunk_size = max(1, self.node_count // len(self.partitions))
        for i, part in enumerate(self.partitions):
            start = i * chunk_size
            end = start + chunk_size
            state = "allocated" if i % 2 == 0 else "idle"
            # Fake the sinfo string format
            lines.append(
                f"node[{start:03d}-{end:03d}]  {chunk_size}   {part:13} {state:7} 64      2:32:1 256000 0        1        (null) none"
            )

        return "\n".join(lines)

    @secretary_tool
    def get_queue_status(self, user: Optional[str] = None) -> str:
        """
        squeue: Returns the list of running and pending jobs.
        """
        header = (
            f"{'JOBID':<8} {'PARTITION':<12} {'USER':<10} {'STATE':<10} {'TIME':<10} {'NODES':<5}"
        )
        lines = [header]

        filtered_jobs = [j for j in self._jobs if not user or j["user"] == user]

        # Show first 50 jobs to avoid massive context bloating
        for j in filtered_jobs[:50]:
            part = self.partitions[0]
            lines.append(
                f"{j['id']:<8} {part:<12} {j['user']:<10} {j['state']:<10} {j['time']:<10} {j['nodes']:<5}"
            )

        if len(filtered_jobs) > 50:
            lines.append(f"... and {len(filtered_jobs) - 50} more jobs.")

        return "\n".join(lines)

    def export_truth(self):
        return {
            "node_count": self.node_count,
            "partitions": self.partitions,
            "job_count": len(self._jobs),
        }
