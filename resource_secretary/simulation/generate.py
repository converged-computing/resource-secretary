import collections
import random
from typing import Any, Dict, Set


class GlobalCatalog:
    """
    Aggregates the union of all resources across 100 mock workers.
    Used to sample realistic parameters for prompt generation.
    We collect the catalog of possible values (across what they can provide).
    While function calls do not change, we should not assume in the future
    that all workers will provision the same discovery functions.
    """

    def __init__(self, fleet_truth: Dict[str, Any]):
        self.fleet_truth = fleet_truth

        # Capability Maps
        self.software: Dict[str, Set[str]] = collections.defaultdict(set)
        self.gpu_models: Set[str] = set()
        self.fabrics: Set[str] = set()
        self.storage_types: Set[str] = set()
        self.mpi_libs: Dict[str, Set[str]] = collections.defaultdict(set)
        self.containers: Set[str] = set()

        # Scale Ranges
        self.max_cores = 0
        self.max_nodes = 0
        self.max_gpus = 0
        self.max_storage_gb = 0

        self.aggregate()

    def aggregate(self):
        """
        Processes the raw JSON truth from all workers into categorized sets.
        """
        # _ is the worker id
        for _, providers in self.fleet_truth.items():
            for category, metadata in providers["truth"].items():
                # This has truth, and the tool registry
                for name, truth in metadata.items():
                    if category == "container":
                        self.containers.add(truth.get("runtime"))

                    elif category == "software":
                        if name == "spack":
                            for pkg in truth.get("manifest", []):
                                app, ver = pkg.split("@")
                                self.software[app].add(ver)

                        elif name == "conda":
                            for _, pkgs in truth.get("environments", {}).items():
                                for pkg in pkgs:
                                    app, ver = pkg.split("@")
                                    self.software[app].add(ver)

                        elif name == "modules":
                            for _, mods in truth.get("modules", {}).items():
                                for mod in mods:
                                    if "/" in mod:
                                        app, ver = mod.split("/")
                                        self.software[app].add(ver)

                    elif category == "hardware":
                        self.max_cores = max(self.max_cores, truth.get("cpus", 0))
                        self.max_gpus = max(self.max_gpus, truth.get("gpus", 0))
                        if truth.get("gpu_model") != "N/A":
                            self.gpu_models.add(truth.get("gpu_model"))

                    elif category == "workload":
                        # Same for flux or slurm
                        self.max_nodes = max(self.max_nodes, truth.get("node_count", 0))
                        # TODO kubeneretes

                    elif category == "network":
                        self.fabrics.add(name)

                    elif category == "storage":
                        self.storage_types.add(name)
                        self.max_storage_gb = max(self.max_storage_gb, truth.get("size_gb", 0))

                    elif category == "parallel":
                        self.mpi_libs[name].add(truth.get("version", "unknown"))


class PromptGenerator:
    """
    Generate prompts with varying specificity.
    The idea here is to also ask different levels in similar ways, because we know the agent will vary based on
    that. We are "pinning" how we ask, but incrementally asking for more or different.
    The index (1..6) is like a specificity index, where 1 is low and 6 is high.
    Each index has three slightly different variants.
    """

    TEMPLATES = {
        1: [  # Just App. I am adding this because I expect it is too little information
            "I need a system with {app} installed.",
            "Does this system have {app}?",
            "I need to run a job with {app}.",
        ],
        2: [  # App + Version OR App + Scale
            "I need to run {app} version {v_range}.",
            "I want a system to run {app} with {count} {unit}",
            "Is {app} available for a {count} {unit} job?",
        ],
        3: [  # App + Version + Scale
            "I need to run {app} {v_range} for a {count} {unit} workload.",
            "I want a system to run {app} ({v_range}) with {count} {unit}.",
            "I need to request {count} {unit} to run {app} {v_range}.",
        ],
        4: [  # App + Version + Scale + [Fabric OR Storage]
            "I need to run {app} {v_range} on {count} {unit} with {fabric} connectivity",
            "I want a system with {storage} storage available for {app} {v_range} using {count} {unit}",
            "I want to request to run {app} {v_range}, on {count} {unit}, and {storage} backend",
        ],
        5: [  # App + Version + Scale + Fabric + Storage
            "I need to run {app} {v_range} on {count} {unit} with {fabric} and {storage}",
            "I want a system to run {app} {v_range}, {count} {unit}, {fabric}, and {storage}",
            "I want to run {app} {v_range} ({count} {unit}) on {fabric} using {storage}",
        ],
        6: [  # Add urgency
            "I need to run {app} {v_range}, {count} {unit}, {fabric}, and {storage} {urgency}.",
            "I want a system to run {app} {v_range} on {count} {unit} ({fabric}/{storage}) {urgency}",
            "I want to immediately run {app} {v_range} with {count} {unit} on {fabric} and {storage}",
        ],
        7: [  # Container technology. Agent needs to decide if app is required LOCALLY (should arguably not be, should be irrelevant)
            "I need to use {app} {v_range} and {runtime}, {count} {unit}, {fabric}, and {storage} {urgency}",
            "I want a system to run {app} {v_range} with {runtime} on {count} {unit} ({fabric}/{storage}) {urgency}",
            "I want to immediately run {app} {v_range} with {runtime} and {count} {unit} on {fabric} and {storage}",
        ],
    }

    def __init__(self, catalog):
        self.catalog = catalog

    def generate_requirement(self) -> Dict[str, Any]:
        """
        Generates a requirement with a random Specificity Index (1-6).
        """
        # Select the specificity
        # We weight it so we get a good spread of easy vs hard
        si = random.choices([1, 2, 3, 4, 5, 6, 7], weights=[5, 20, 30, 20, 10, 10, 5])[0]

        # Number of gpus - let's ask for GPU 80% of the time. When we ask, do AND or OR
        gpu_count = get_gpu_count()
        gpu_requires = "NONE"
        gpu_desc = ""
        if gpu_count > 0:
            # If we ask for GPUs, ask for AND or OR
            gpu_requires = random.choice(["OR", " AND"])
            gpu_desc = f" to run on CPU {gpu_requires} {gpu_count} GPU per node"

        # Sample data
        app = random.choice(list(self.catalog.software.keys()))
        version = random.choice(list(self.catalog.software[app]))
        op = random.choice([">=", "==", "<="])
        unit = random.choice(["cores", "nodes"])
        count = random.randint(
            1,
            max(
                1,
                int(
                    self.catalog.max_cores * 0.7
                    if unit == "cores"
                    else self.catalog.max_nodes * 0.7
                ),
            ),
        )
        fabric = random.choice(list(self.catalog.fabrics))
        storage = random.choice(list(self.catalog.storage_types))
        urgency_type = random.choice(["immediate", "relaxed"])
        urgency_text = "right now" if urgency_type == "immediate" else "later"

        # Assume if we have mpi and low latency network... not specific about mpi variant for now
        has_mpi = random.choice([True, False])

        # Fill logic based on specificity
        logic = {"software": {"name": app}}
        if si >= 2:
            logic["software"]["version"] = version
            logic["software"]["op"] = op
        if si >= 3:
            # unit will be nodes or cores here.
            logic["compute"] = {
                "count": count,
                "unit": unit,
                "gpus": gpu_count,
                "gpu_requires": gpu_requires,
            }
        if si >= 4:
            logic["network"] = fabric
        if si >= 5:
            logic["storage"] = storage
        if si >= 6:
            logic["temporal"] = {"urgency": urgency_type}

        # Select container runtime requirement (SI 7)
        runtime = random.choice(["docker", "singularity", "podman"])
        if si == 7:
            logic["container"] = {"runtime": runtime}
        if has_mpi:
            logic["parallel"] = {"mpi": True}

        # Pick a template matching the SI and format it safely
        prompt_style_index = random.choice(range(0, 3))
        template = self.TEMPLATES[si][prompt_style_index]
        prompt_text = template.format(
            app=app,
            v_range=f"{op} {version}",
            count=count,
            unit=unit,
            fabric=fabric,
            storage=storage,
            urgency=urgency_text,
            runtime=runtime,
        )
        if has_mpi:
            prompt_text += " with support for low latency MPI"
        prompt_text += gpu_desc

        return {
            "prompt": prompt_text.strip(),
            "style_index": prompt_style_index,
            "specificity_index": si,
            "logic": logic,
        }


def get_gpu_count():
    # This is dumb, but 80% of time let's ask for GPUs, and then select from 1-8 per node
    # Choices: 1-8 (80% total), 0 (20% fallback - change 0 to desired value)
    result = random.choices(["1-8", "none"], weights=[80, 20], k=1)[0]

    if result == "1-8":
        return random.randint(1, 8)
    else:
        return 0
