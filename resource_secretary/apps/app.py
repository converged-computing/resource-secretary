# Note that this base provides probe, etc.
from dataclasses import dataclass
from typing import Callable, Dict

from resource_secretary.providers import get_providers
from resource_secretary.providers.provider import BaseProvider

from .prompts import AppPromptGenerator


@dataclass
class PromptMatrix:
    application: str
    matrix: str
    manager: dict


class BaseApplication(BaseProvider):
    is_provider = True

    def __init__(self, *args, **kwargs):
        self.category = "application"
        self.default_workload = None
        super().__init__(*args, **kwargs)

    def get_prompt_matrix(self, flatten=False, filters=None, **params) -> dict:
        """
        The standard entry point for generating test matrices.
        Returns {} if the subclass does not implement templates.
        """
        templates = self.get_prompt_templates()

        # We can either generate faux or accept from the user in params
        truth = self.get_ground_truth_commands(**params)
        if not templates or not truth:
            return {}

        return AppPromptGenerator.generate(templates, truth, params, flatten, filters)

    def __init__(self, **kwargs):
        self.workloads = {}
        self.modifiers = {}
        self.default_workoad = None

    def get_prompt_templates(self, workload=None, manager="flux"):
        """
        Given a workload manager template and workload, derive templates.
        Default to flux, and we require the user provided /app to set a default.
        """
        workload_name = workload or self.default_workload
        if not workload_name:
            raise ValueError(f"Application '{self.name}' does not have a default workload.")

        # Discover the manager provider data
        manager_data = {}
        for instance in get_providers(categories=["workload"]).get("workload", []):
            if instance.name.lower() == manager.lower():
                manager_data = instance.get_prompt_vocabulary()
                break

        if not manager_data:
            raise ValueError(f"Workload manager '{manager}' not found in providers.")

        # manager and resources come from the provider
        templates = {
            "manager": {"variants": manager_data["manager"]},
            "resources": {"variants": manager_data["resources"]},
            "app_config": workload,
        }

        # modifiers are typically flags, but can be other things
        for mod_name, mod_data in self.modifiers.items():
            templates[f"modifier_{mod_name}"] = mod_data

        # manager modifiers are the same (e.g., cpu affinity for flux)
        # When we add gpu_affinity, a filter can be used to leave it out for prompts
        for mod_name, mod_data in manager_data.get("modifiers", {}).items():
            templates[f"modifier_{mod_name}"] = mod_data

        return PromptMatrix(self.name, templates, manager_data)

    def get_prompt_matrix(self, workload: str, manager: str, **params):
        """
        The standard entry point for all applications.
        """
        raise NotImplementedError

    def get_ground_truth_commands(self, **params) -> dict:
        """
        Override in subclass to provide baseline commands.
        """
        return {}
