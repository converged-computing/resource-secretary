import datetime
from typing import Any, Dict, List

from ...provider import secretary_tool
from ..base import MockBaseProvider

year = datetime.date.today().year

# (min_major, max_major, min_minor, max_minor)
packages = {
    # Compilers, mpi
    "gcc": (9, 14, 1, 3),
    "llvm": (12, 18, 0, 1),
    "openmpi": (3, 5, 0, 1),
    "cuda": (11, 12, 0, 8),
    "python": (3, 8, 10, 12),
    "mpich": (3, 4, 1, 3),
    "mvapich2": (2, 3, 3, 7),
    "cray-mpich": (7, 8, 0, 7),
    # Benchmarks and mini-apps
    # LOL amg WHY DID YOU PIN A YEAR
    "amg2023": (2023, 2023, 1, 1),
    "hpl": (2, 2, 3, 3),
    "hpcg": (3, 3, 1, 1),
    "lulesh": (2, 2, 0, 4),
    "kripke": (1, 1, 2, 4),
    "laghos": (3, 3, 1, 1),
    "quicksilver": (1, 1, 0, 2),
    "rajaperf": (0, 2022, year, year),
    "miniamr": (1, 1, 0, 0),
    "minife": (2, 2, 1, 1),
    "pennant": (1, 1, 0, 1),
    "stream": (5, 5, 10, 10),
    "osu-benchmarks": (5, 7, 1, 3),
    "nccl-tests": (2, 2, 15, 21),
    "mixbench": (1, 1, 0, 0),
    "gpcnet": (1, 1, 3, 5),
    "mt-gemm": (1, 1, 0, 0),
    # Apps
    "gromacs": (2019, year, 1, 6),
    "lammps": (2020, year, 1, 12),
    "mfem": (4, 4, 4, 7),
    "nekrs": (22, 23, 0, 0),
    "qmcpack": (3, 3, 15, 17),
    "smilei": (4, 5, 0, 8),
    "samurai": (2022, year, 0, 0),
    "t8code": (1, 2, 0, 0),
    "remhos": (1, 1, 0, 0),
    "likwid": (5, 5, 2, 3),
    "ior": (3, 4, 0, 1),
    "fio": (3, 3, 20, 36),
    "cortex": (1, 1, 0, 5),
    "chatterbug": (1, 1, 0, 0),
    "phloem": (1, 1, 0, 0),
    "mpi4jax": (0, 0, 4, 15),
    "e3sm-kernels": (1, 1, 0, 3),
    "gamess-r1-mp2-miniapp": (2020, year, 1, 1),
    "bdas": (1, 2, 0, 5),
    "cfdscope": (0, 1, 0, 5),
}


class MockSpackProvider(MockBaseProvider):
    """
    Expert Mock: Generates a software environment.
    Primary Anchor: Density (Variety/Complexity).
    Volatility: High (0.4) - Softare stacks vary wildly between systems.
    """

    def __init__(self, config):
        super().__init__(config)
        self.packages: List[Dict[str, Any]] = []
        self.root = "/opt/spack"
        self.version = "unknown"
        self.arch = "unknown"
        self.available = False

    @property
    def name(self) -> str:
        return "spack"

    def probe(self) -> bool:
        """
        The Spack Expert realizes its state by interpreting the worker's density.
        I am choosing density for most of these because a package install is informationally
        rich. It's not just a number of packages - there are variants, metadata, etc.
        """
        # Create a stable RNG for this specific provider
        rng = self.config.get_rng("spack")

        # Identity Metadata
        self.version = f"0.{rng.randint(18, 22)}.{rng.randint(0, 4)}"
        self.arch = f"linux-ubuntu22.04-{rng.choice(['zen3', 'skylake', 'icelake'])}"

        # use density target, but allow for high volatility (0.4)
        # this allows a dense worker to occasionally have a sparse software stack.
        self.package_count = self.generate("software_packages", mode="density", volatility=0.4)
        self.packages = []

        # Determine how many unique software names to pick
        # We pick a subset of the catalog based on the count
        catalog_names = list(packages.keys())
        num_names = min(self.package_count, len(catalog_names))
        selected_names = rng.sample(catalog_names, k=num_names)

        for name in selected_names:
            min_v, max_v, min_m, max_m = packages[name]

            # Occasionally install multiple versions of the same app
            # LOL as I am writing this, SO MUCH TRUTH 😂😭
            num_versions = rng.choices([1, 2, 3], weights=[80, 15, 5])[0]
            for _ in range(num_versions):
                self.packages.append(
                    {
                        "name": name,
                        "version": f"{rng.randint(min_v, max_v)}.{rng.randint(min_m, max_m)}.{rng.randint(0, 9)}",
                        "arch": {"platform": "linux", "target": self.arch.split("-")[-1]},
                        "compiler": {"name": "gcc", "version": f"{rng.randint(10, 12)}.1.0"},
                        "variants": {
                            "mpi": rng.choice([True, False]),
                            "cuda": rng.choice([True, False]),
                            "shared": True,
                        },
                        "hash": "".join(rng.choices("abcdef0123456789", k=8)),
                    }
                )

        self.available = True
        return True

    @property
    def metadata(self) -> Dict[str, Any]:
        if not self.available:
            return {"installed": False}
        return {
            "root": self.root,
            "version": self.version,
            "target_arch": self.arch,
            "package_count": len(self.packages),
        }

    # Secretary Tools (match the real SpackProvider interface but we are cheating, faux calls)

    @secretary_tool
    def find_package(self, query: str) -> Any:
        """
        Searches for installed Spack packages matching the query.
        """
        matches = [p for p in self.packages if query.lower() in p["name"].lower()]
        return matches if matches else {"message": f"No matches found for {query}."}

    @secretary_tool
    def get_package_info(self, name: str) -> str:
        """
        Retrieves spack info for a specific package name.
        """
        if name not in packages:
            return f"No package info found for '{name}'."

        # TODO can we make this more realistic?
        return (
            f"Package: {name}\n"
            f"Description: Procedural mock for {name}.\n"
            f"Versions: Latest {CURRENT_YEAR}.1.0\n"
            f"Variants: [mpi, cuda, debug, shared]"
        )

    def export_truth(self) -> Dict[str, Any]:
        """
        The gold standard for accuracy calculation.
        """
        return {
            "version": self.version,
            "total_packages": len(self.packages),
            "manifest": [f"{p['name']}@{p['version']}" for p in self.packages],
        }
