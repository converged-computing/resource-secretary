from typing import Any, Dict

from ...provider import secretary_tool
from ..base import MockBaseProvider

# A pool of obscure MCA parameters to simulate 'Density' noise
MCA_PARAMETER_POOL = [
    "btl_tcp_if_include",
    "pml_ucx_verbose",
    "coll_tuned_use_dynamic_rules",
    "osc_pt2pt_no_locks",
    "mpi_warn_on_fork",
    "btl_openib_allow_ib",
    "oob_tcp_if_include",
    "rmaps_base_mapping_policy",
    "hwloc_base_binding_policy",
    "mca_base_component_show_load_errors",
    "shmem_mmap_relocate_backing_file",
]


class MockOpenMPIProvider(MockBaseProvider):
    """
    Mock: OpenMPI.
    Scale: Max Procs/Ranks.
    Density: MCA Parameter complexity (noise).
    """

    def __init__(self, config):
        super().__init__(config)
        self.version = "unknown"
        self._mca_params = {}
        self._extra_mca = []

    @property
    def name(self) -> str:
        return "openmpi"

    def probe(self) -> bool:
        rng = self.config.get_rng("openmpi")
        self.version = rng.choice(["4.1.4", "4.1.5", "5.0.0", "5.0.1"])

        # Density to determine how many params to show
        # High density = many obscure parameters (noise)
        num_mca = max(1, int(len(MCA_PARAMETER_POOL) * self.config.targets["density"]))
        self._extra_mca = rng.sample(MCA_PARAMETER_POOL, k=num_mca)

        # Scale driven core parameters
        # Max procs scales with the system size
        node_count = self.generate("nodes", mode="scale")
        self._mca_params = {
            "pml": rng.choice(["ucx", "ob1", "cm"]),
            "btl": rng.sample(["tcp", "self", "vader", "openib"], k=rng.randint(2, 3)),
            "max_procs": node_count * 64,
        }

        self.available = True
        return True

    @property
    def metadata(self) -> Dict[str, Any]:
        return {"version": self.version, "mca_pml": self._mca_params["pml"]}

    @secretary_tool
    def get_mpi_info(self) -> str:
        """Mock ompi_info: Returns version and build configuration."""
        output = [
            f"Open MPI: {self.version}",
            f"Open MPI repo revision: v{self.version}",
            f"Prefix: /opt/openmpi/{self.version}",
            f"Configured with: --with-ucx --with-device-libfabric",
        ]

        # Inject the 'Density' noise: show the obscure MCA parameters
        output.append("\n--- Advanced MCA Parameters ---")
        for param in self._extra_mca:
            output.append(f"MCA {param}: value=1 (source: environment)")

        return "\n".join(output)

    @secretary_tool
    def check_fabric_support(self) -> Dict[str, Any]:
        """
        Returns the active Byte Transport Layers (BTL) and matching logic.
        """
        return {
            "pml": self._mca_params["pml"],
            "btl": self._mca_params["btl"],
            "max_supported_procs": self._mca_params["max_procs"],
        }

    def export_truth(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "pml": self._mca_params["pml"],
            "extra_mca_count": len(self._extra_mca),
        }
