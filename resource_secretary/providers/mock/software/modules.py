from typing import Any, Dict, List

from ...provider import secretary_tool
from ..base import MockBaseProvider

MODULE_CATALOG = {
    "Compilers": [
        "gcc/9.4.0",
        "gcc/11.2.0",
        "gcc/12.1.0",
        "intel/2021.4.0",
        "intel/2023.1.0",
        "nvhpc/22.7",
        "nvhpc/23.1",
        "clang/14.0.6",
        "aocc/3.2.0",
    ],
    "MPI": [
        "openmpi/4.1.4",
        "openmpi/5.0.0",
        "mpich/3.4.3",
        "mpich/4.0.2",
        "mvapich2/2.3.7",
        "intel-mpi/2021.7.1",
    ],
    "Libraries": [
        "hdf5/1.12.2",
        "netcdf-c/4.8.1",
        "fftw/3.3.10",
        "boost/1.79.0",
        "metis/5.1.0",
        "petsc/3.17.4",
        "trilinos/13.4.1",
        "gsl/2.7",
        "eigen/3.4.0",
    ],
    "Math/AI": [
        "cuda/11.7",
        "cuda/12.1",
        "cudnn/8.4.1",
        "nccl/2.12.12",
        "pytorch/2.0.1",
        "tensorflow/2.12.0",
        "magma/2.6.2",
    ],
    "Apps": [
        "lammps/20220623",
        "gromacs/2021.5",
        "namd/2.14",
        "vasp/6.3.1",
        "quantum-espresso/7.0",
        "cp2k/9.1",
        "nwchem/7.0.2",
        "openfoam/2212",
    ],
    "Tools": [
        "cmake/3.23.1",
        "git/2.37.1",
        "ninja/1.11.0",
        "valgrind/3.19.0",
        "likwid/5.2.2",
        "darshan/3.4.0",
        "gdb/12.1",
    ],
}


class MockModuleProvider(MockBaseProvider):
    """
    Expert Mock: Environment Modules (Lmod/TCL).
    Anchor: Density (Number of available modules).
    Volatility: Medium (0.3).
    """

    def __init__(self, config):
        super().__init__(config)
        self._available_modules: Dict[str, List[str]] = {}
        self.module_type = "lmod"
        self.available = False

    @property
    def name(self) -> str:
        return "modules"

    def probe(self) -> bool:
        """
        The Modules Expert generates its available list based on Density.
        """
        rng = self.config.get_rng("modules")

        # 1. Determine how many modules to 'reveal' (Density driven)
        # Use our standard generate method
        total_to_pick = self.generate("software_packages", mode="density", volatility=0.2)

        # 2. Populate from the Catalog
        self._available_modules = {}
        count_per_cat = max(1, total_to_pick // len(MODULE_CATALOG))

        for category, modules in MODULE_CATALOG.items():
            # Pick a subset of modules from each category
            num = min(len(modules), count_per_cat)
            self._available_modules[category] = rng.sample(modules, k=num)

        self.available = True
        return True

    @property
    def metadata(self) -> Dict[str, Any]:
        return {
            "module_system_type": self.module_type,
            "modulepath": [f"/opt/modulefiles/{self.config.system_name}/core"],
            "total_modules": sum(len(v) for v in self._available_modules.values()),
        }

    @secretary_tool
    def list_available_modules(self, query: str = "") -> str:
        """
        Mock output of 'module avail'.
        Returns a categorized list of strings mimicking Lmod output.
        """
        output = []
        for category, modules in self._available_modules.items():
            # Filter by query if present
            filtered = [m for m in modules if query.lower() in m.lower()]
            if not filtered and query:
                continue

            output.append(f"\n--- /opt/modulefiles/{category} ---")
            # Mimic Lmod's multi-column or simple list output
            for m in sorted(filtered):
                # Add a (D) for default to some of them for realism
                default = " (D)" if "/12." in m or "/2023" in m else ""
                output.append(f"  {m}{default}")

        if not output or (query and len(output) == 0):
            return f"No modules found matching: {query}"

        return "\n".join(output)

    @secretary_tool
    def get_module_details(self, module_name: str) -> str:
        """
        Mock output of 'module spider' or 'module show'.
        """
        # Find if the module exists in our truth
        found = False
        for cat_list in self._available_modules.values():
            if module_name in cat_list:
                found = True
                break

        if not found:
            return f"Lmod has not found any existing module named '{module_name}'."

        return (
            f"----------------------------------------------------------\n"
            f"  {module_name}:\n"
            f"----------------------------------------------------------\n"
            f"    Description: Procedural mock for {module_name}.\n"
            f"    This module provides the environment for {module_name.split('/')[0]}.\n"
            f"\n    Help:\n"
            f"      Sets PATH and LD_LIBRARY_PATH for {module_name}."
        )

    def export_truth(self) -> Dict[str, Any]:
        """
        Ground Truth for accuracy calculation.
        """
        return {"type": self.module_type, "modules": self._available_modules}
