from typing import Any, Dict, List

from ...provider import secretary_tool
from ..base import MockBaseProvider

# Extensive Python/Conda package library
CONDA_PACKAGES = [
    # AI/ML
    "torch",
    "torchvision",
    "torchaudio",
    "tensorflow",
    "keras",
    "scikit-learn",
    "transformers",
    "accelerate",
    "diffusers",
    "sentence-transformers",
    "xgboost",
    "lightgbm",
    # Data Science & Stats
    "numpy",
    "scipy",
    "pandas",
    "polars",
    "dask",
    "xarray",
    "statsmodels",
    "networkx",
    "numba",
    # Visualization
    "matplotlib",
    "seaborn",
    "plotly",
    "bokeh",
    "altair",
    "pyvista",
    # HPC & Parallel
    "mpi4py",
    "dask-mpi",
    "ray",
    "horovod",
    "cupy",
    "pycuda",
    # Bioinformatics & Science
    "biopython",
    "scanpy",
    "anndata",
    "rdkit",
    "ase",
    "pymatgen",
    "bioconda-utils",
    # Web, API & Tools
    "flask",
    "fastapi",
    "requests",
    "aiohttp",
    "sqlalchemy",
    "pydantic",
    "click",
    "tqdm",
    # Development
    "black",
    "pytest",
    "ipykernel",
    "notebook",
    "jupyterlab",
    "nbconvert",
    "ipywidgets",
]

# Archetypal environments to make the search space "make sense"
ENV_TEMPLATES = {
    "base": ["python", "pip", "conda", "requests", "tqdm"],
    "ml-gpu": ["python", "torch", "torchvision", "transformers", "numpy", "cupy"],
    "data-science": ["python", "pandas", "scikit-learn", "matplotlib", "seaborn", "jupyterlab"],
    "bio-info": ["python", "biopython", "scanpy", "anndata", "pandas", "dask"],
    "hpc-dev": ["python", "mpi4py", "numba", "cython", "cmake", "pytest"],
}


class MockCondaProvider(MockBaseProvider):
    """
    Conda/Mamba.
    Density (Variety of environments and packages).
    Volatility: High (0.5).
    """

    def __init__(self, config):
        super().__init__(config)
        self._envs: Dict[str, Dict[str, Any]] = {}
        self.available = False

    @property
    def name(self) -> str:
        return "conda"

    def probe(self) -> bool:
        rng = self.config.get_rng("conda")

        # Determine how many environments exist (Density driven)
        # High density = 8-10 envs, Low density = 1-2 envs
        num_envs = max(1, int(len(ENV_TEMPLATES) * 2 * self.config.targets["density"]))

        # Build the environments
        self._envs = {}
        for i in range(num_envs):
            # Pick a template or make a random one
            template_name = rng.choice(list(ENV_TEMPLATES.keys()))
            env_name = f"{template_name}-{i}" if i > 0 else template_name

            # Base packages from template
            packages = list(ENV_TEMPLATES[template_name])

            # Add "Noise" packages based on Density
            noise_count = int(10 * self.config.targets["density"])
            extra_pkgs = rng.sample(CONDA_PACKAGES, k=min(noise_count, len(CONDA_PACKAGES)))

            # Combine and deduplicate
            final_pkgs = sorted(list(set(packages + extra_pkgs)))

            self._envs[env_name] = {
                "name": env_name,
                "path": f"/home/mockuser/miniconda3/envs/{env_name}",
                "packages": [
                    {
                        "name": p,
                        "version": f"{rng.randint(0, 3)}.{rng.randint(0, 15)}.{rng.randint(0, 9)}",
                    }
                    for p in final_pkgs
                ],
            }

        self.available = True
        return True

    @property
    def metadata(self) -> Dict[str, Any]:
        return {"system_type": "conda", "env_count": len(self._envs), "version": "conda 23.7.4"}

    @secretary_tool
    def list_environments(self) -> Dict[str, Any]:
        """
        Lists all discovered Conda environment paths.
        """
        return {"envs": [e["path"] for e in self._envs.values()]}

    @secretary_tool
    def list_packages(self, env_name: str) -> List[Dict[str, Any]]:
        """
        Lists installed packages in a specific environment.
        Returns the exact JSON format the real CondaProvider would return.
        """
        # Support searching by name or full path
        for name, data in self._envs.items():
            if env_name == name or env_name == data["path"]:
                return data["packages"]
        return []

    def export_truth(self) -> Dict[str, Any]:
        """
        Ground Truth for accuracy calculation.
        """
        return {
            "total_envs": len(self._envs),
            "environments": {
                name: [f'{p["name"]}@{p["version"]}' for p in d["packages"]]
                for name, d in self._envs.items()
            },
        }
