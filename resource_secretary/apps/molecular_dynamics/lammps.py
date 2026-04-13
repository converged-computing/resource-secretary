from resource_secretary.apps.app import BaseApplication
from resource_secretary.apps.prompts import AppPromptGenerator
from resource_secretary.providers import get_providers

LAMMPS_WORKLOADS = {
    "reaxff": {
        "syntax": "{bin} -v x {x} -v y {y} -v z {z} -in {input}",
        "defaults": {"x": 32, "y": 32, "z": 16, "input": "in.reaxff.hns"},
        "variants": {
            "exact": "{bin} -v x {x} -v y {y} -v z {z} -in {input}",
            "verbatim": "with the {bin} command with variables x={x}, y={y}, z={z} and input {input}",
            "descriptive": "and the HNS simulation on a {x}x{y}x{z} grid using the {input} file",
        },
    },
    "lj": {
        "syntax": "{bin} -in in.lj",
        "defaults": {"input": "in.lj"},
        "variants": {
            "exact": "{bin} -v x {x} -v y {y} -v z {z} -in {input}",
            "verbatim": "run the {bin} command with variables x={x}, y={y}, z={z} and input {input}",
            "descriptive": "run the HNS simulation on a {x}x{y}x{z} grid using the {input} file",
        },
    },
}

LAMMPS_MODIFIERS = {
    "nocite": {
        "metadata": {"type": "app", "flag": "-nocite"},
        "variants": {
            "exact": "with the -nocite flag",
            "verbatim": "including the -nocite argument",
            "descriptive": "and suppress the citation output",
        },
    }
}


class LammpsApplication(BaseApplication):
    """
    LAMMPS: Large-scale Atomic/Molecular Massively Parallel Simulator.
    Supports multiple internal workloads (ReaxFF, LJ, etc.) and modifiers.
    """

    @property
    def name(self):
        return "lammps"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.workloads = LAMMPS_WORKLOADS
        self.modifiers = LAMMPS_MODIFIERS
        self.default_workload = "reaxff"

    def get_prompt_matrix(
        self, workload="reaxff", manager="flux", flatten=False, filters=None, count=None, **params
    ):
        """
        Get a specific configuration for lammps
        """
        workload = self.workloads[workload]

        # Setup Params
        final_params = {"bin": "lmp", "nodes": 1, "tasks": 1}
        final_params.update(workload.get("defaults", {}))
        final_params.update(params)

        # Get Templates
        templates = self.get_prompt_templates(workload, manager)

        # Build Truth Template
        m_syntax = templates.manager["syntax"]
        app_syntax = workload["syntax"]
        truth = f"{m_syntax['run_cmd']} {{manager_mods}} {m_syntax['resource_flags']} {app_syntax} {{app_mods}}"
        return AppPromptGenerator.generate(
            templates, truth, final_params, flatten, filters, count=count
        )
