from typing import Any, Dict, List

from ...provider import secretary_tool
from ..base import MockBaseProvider

# Significantly expanded PyPI library for ML, Science, and Domain-Specific Research
PIP_PACKAGES = [
    "torch",
    "tensorflow",
    "jax",
    "jaxlib",
    "flax",
    "pytorch-lightning",
    "transformers",
    "datasets",
    "evaluate",
    "diffusers",
    "accelerate",
    "peft",
    "bitsandbytes",
    "vllm",
    "trl",
    "timm",
    "sentence-transformers",
    "langchain",
    "llama-index",
    "haystack-ai",
    "chromadb",
    "pinecone-client",
    "onnx",
    "onnxruntime-gpu",
    "tensorrt",
    "deepspeed",
    "horovod",
    "keras",
    "keras-nlp",
    "keras-cv",
    "fastai",
    "catalyst",
    "optuna",
    "ray",
    "mlflow",
    "wandb",
    "clearml",
    "dvc",
    "numpy",
    "pandas",
    "scipy",
    "scikit-learn",
    "polars",
    "pyarrow",
    "duckdb",
    "dask",
    "modin",
    "xarray",
    "statsmodels",
    "patsy",
    "xgboost",
    "lightgbm",
    "catboost",
    "imbalanced-learn",
    "numba",
    "cython",
    "numexpr",
    "bottleneck",
    "fenics",
    "u_flot",
    "petsc4py",
    "slepc4py",
    "mpi4py",
    "pyopencl",
    "pycuda",
    "cupy-cuda12x",
    "netcdf4",
    "h5py",
    "zarr",
    "pydap",
    "pint",
    "uncertainties",
    "biopython",
    "scanpy",
    "anndata",
    "squidpy",
    "pyscenic",
    "scrublet",
    "rdkit",
    "deepchem",
    "mendeleev",
    "periodic-table",
    "pubchempy",
    "openbabel",
    "pyscf",
    "psi4",
    "mdeval",
    "prody",
    "ase",
    "pymatgen",
    "phonopy",
    "hiphive",
    "amusetest",
    "ovito",
    "mdtraj",
    "mdanalysis",
    "openmm",
    "lammps",
    "feynman",
    "astropy",
    "sunpy",
    "yt",
    "metpy",
    "plasmapy",
    "matplotlib",
    "seaborn",
    "plotly",
    "bokeh",
    "altair",
    "hvplot",
    "pyvista",
    "itkwidgets",
    "mayavi",
    "gradio",
    "streamlit",
    "dash",
    "fastapi",
    "flask",
    "django",
    "uvicorn",
    "pydantic",
    "sqlalchemy",
    "requests",
    "httpx",
    "aiohttp",
    "grpcio",
    "protobuf",
    "black",
    "pytest",
    "tqdm",
    "click",
    "loguru",
    "rich",
    "typer",
]

# Thematic installation templates to mimic realistic environment setups
INSTALL_TEMPLATES = {
    "llm-ops": [
        "transformers",
        "accelerate",
        "peft",
        "bitsandbytes",
        "vllm",
        "trl",
        "sentence-transformers",
    ],
    "bio-genomics": ["biopython", "scanpy", "anndata", "squidpy", "pandas", "numpy"],
    "materials-sim": ["ase", "pymatgen", "rdkit", "pyscf", "openmm", "mpi4py"],
    "hpc-physics": ["fenics", "petsc4py", "slepc4py", "mpi4py", "h5py", "numba"],
    "geo-spatial": ["xarray", "netcdf4", "dask", "metpy", "astropy", "pyvista"],
    "classical-ds": ["pandas", "scikit-learn", "matplotlib", "seaborn", "xgboost", "statsmodels"],
}


class MockPipProvider(MockBaseProvider):
    """
    Mock Pip Provider.
    Simulates site-packages discovery across multiple Python installations.
    Density: Governs the number of installations and the depth of the package lists.
    Volatility: High (0.5).
    """

    def __init__(self, config):
        super().__init__(config)
        self._installs: Dict[str, Dict[str, Any]] = {}
        self.available = False

    @property
    def name(self) -> str:
        return "pip"

    def probe(self) -> bool:
        rng = self.config.get_rng("pip")

        # Determine how many installations exist based on Density (1 to 12)
        num_installs = max(1, int(len(INSTALL_TEMPLATES) * 2 * self.config.targets["density"]))

        self._installs = {}
        for i in range(num_installs):
            # Rotate through templates
            keys = list(INSTALL_TEMPLATES.keys())
            template_key = keys[i % len(keys)]

            # Generate installation metadata
            install_name = f"{template_key}-{i}" if i >= len(keys) else template_key
            install_path = f"/usr/local/lib/python3.10/site-packages/{install_name}"

            # Start with thematic base packages
            packages = list(INSTALL_TEMPLATES[template_key])

            # Add significant "Noise" (secondary dependencies/tools) based on Density
            # Higher density = more shared/interdisciplinary packages
            noise_count = int(40 * self.config.targets["density"])
            extra_pkgs = rng.sample(PIP_PACKAGES, k=min(noise_count, len(PIP_PACKAGES)))

            final_pkgs = sorted(list(set(packages + extra_pkgs)))

            self._installs[install_name] = {
                "name": install_name,
                "location": install_path,
                "packages": [
                    {
                        "name": p,
                        "version": f"{rng.randint(0, 4)}.{rng.randint(0, 30)}.{rng.randint(0, 15)}",
                    }
                    for p in final_pkgs
                ],
            }

        self.available = True
        return True

    @property
    def metadata(self) -> Dict[str, Any]:
        """
        Metadata formatted specifically for the agent to parse system state.
        """
        return {
            "system_type": "pip",
            "installs_count": len(self._installs),
            "total_package_indices": sum(len(i["packages"]) for i in self._installs.values()),
            "version": "pip 24.0",
        }

    @secretary_tool
    def list_installations(self) -> Dict[str, Any]:
        """
        Lists all discovered Python installation locations.
        """
        return {"installations": [i["location"] for i in self._installs.values()]}

    @secretary_tool
    def list_packages(self, install_name: str) -> List[Dict[str, Any]]:
        """
        Lists installed packages for a specific installation name or path.
        """
        for name, data in self._installs.items():
            if install_name == name or install_name == data["location"]:
                return data["packages"]
        return []

    def export_truth(self) -> Dict[str, Any]:
        """
        Ground Truth used for calculating the accuracy/consistency of agent reasoning.
        """
        # These are technically installs, but we call envs to be consistent with conda
        return {
            "total_installs": len(self._installs),
            "installs": {
                name: [f'{p["name"]}@{p["version"]}' for p in d["packages"]]
                for name, d in self._installs.items()
            },
        }
