import importlib
import inspect
import logging
import os
import pkgutil
import random
from typing import Dict, List, Union

from .archetype import CloudArchetype, HPCArchetype, StandaloneArchetype
from .base import MockBaseProvider
from .config import MockConfig

logger = logging.getLogger(__name__)

archetypes = {"hpc": HPCArchetype, "cloud": CloudArchetype, "standalone": StandaloneArchetype}


def discover_mock_providers(
    worker_id: str, choice: Union[bool, str] = True
) -> List[MockBaseProvider]:
    """
    Discovery logic akin to the real provider discovery.
    Returns a dictionary of mock classes grouped by category.
    We require the worker id and archetype because discovery
    depends on those things.
    """
    seed = abs(hash(worker_id))
    rng = random.Random(seed)

    # Select the archetype (this is like an identity to inform randomization / state)
    archetype_name = select_archetype(seed, choice)
    archetype = archetypes.get(archetype_name, StandaloneArchetype)()

    # Create the worker config from it, we need archetype and seed
    config = MockConfig(seed=seed, archetype=archetype)

    # Discover mock provider classes
    class_catalog = find_provider_classes()

    # Compose the worker based on the archetype's cardinality
    # Example - an HPC cluster usually has one workload manager (provider)
    worker_providers = {}

    # Each archetype knows its own slots (min/max/choices)
    for category, constraints in archetype.slots.items():
        discovered_classes = class_catalog.get(category, [])

        # Filter for classes permitted by this specific archetype
        valid_options = [
            cls for cls in discovered_classes if cls.__name__ in constraints["choices"]
        ]

        if not valid_options:
            if constraints.get("min", 0) > 0:
                logger.warning(f"Required slot '{category}' has no valid discovered mocks.")
            continue

        # Enforce Cardinality (min/max)
        upper = min(constraints["max"], len(valid_options))
        lower = min(constraints["min"], upper)
        num_to_pick = rng.randint(lower, upper)

        # womp womp
        if num_to_pick == 0:
            continue

        # Pick the providers for this worker
        chosen_classes = rng.sample(valid_options, k=num_to_pick)

        for cls in chosen_classes:
            # Every mock provider is created with the config
            instance = cls(config)
            instance.category = category

            # The provider uses its expertise to interpret the config and generate its internal state.
            # E.g, spack knows to generate itself with packages, etc.
            if instance.probe():
                if category not in worker_providers:
                    worker_providers[category] = []
                worker_providers[category].append(instance)

    return worker_providers


def select_archetype(seed, choice=True):
    """
    Handles archetype selection logic
    """
    rng = random.Random(seed)

    # Validate archetype. In the future, we can allow user to define custom.
    # This will work for now.
    valid_archetypes = list(archetypes.keys())

    # User passed --mock
    if choice is True:
        selected = rng.choices(valid_archetypes, weights=[40, 40, 20], k=1)[0]
        logger.info(f"🎲 Random Mock Archetype Roll: {selected}")
        return selected

    # If we get here, we have a string
    # User passed --mock <name>
    choice = choice.lower()
    if choice in valid_archetypes:
        logger.info(f"🎯 Explicit Mock Archetype: {choice}")
        return choice

    # If they are thinking something exists that does not,
    # they should know about it.
    raise ValueError(f"{choice} is not a known archetype. Choices: {valid_archetypes}")


def find_provider_classes() -> Dict[str, List[MockBaseProvider]]:
    """
    Discovery logic akin to the real provider discovery.
    Returns a dictionary of mock classes grouped by category.
    """
    mock_pkg_path = os.path.dirname(__file__)
    catalog = {}

    # Walk the subdirectories under providers/mock/
    for entry in os.scandir(mock_pkg_path):
        if entry.is_dir() and not entry.name.startswith("__"):
            category = entry.name
            full_pkg_path = f"{__name__}.{category}"

            # Walk modules in the category directory
            for _, mod_name, _ in pkgutil.walk_packages([entry.path], f"{full_pkg_path}."):
                module = importlib.import_module(mod_name)

                for _, obj in inspect.getmembers(module, inspect.isclass):

                    # Filter for classes that inherit from MockBaseProvider
                    if (
                        issubclass(obj, MockBaseProvider)
                        and obj is not MockBaseProvider
                        and getattr(obj, "is_provider", True)
                    ):

                        if category not in catalog:
                            catalog[category] = []
                        catalog[category].append(obj)
    return catalog
