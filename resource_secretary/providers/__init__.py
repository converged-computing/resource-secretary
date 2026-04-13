import importlib
import inspect
import os
import pkgutil
import re
from typing import Dict, List

from .provider import BaseProvider


def find_provider_classes(root_path=None):
    """
    Public generator that walks the provider tree and yields categories and classes
    that are marked with is_provider=True.
    """
    # Allow for discovery anywhere, default to providers here
    root_path = root_path or os.path.dirname(__file__)

    # Assumes under resource secretary
    name = "resource_secretary." + os.path.basename(root_path)
    for entry in os.scandir(root_path):
        # Don't include hidden or mock
        if entry.is_dir() and not re.search("(__|mock)", entry.name):
            category = entry.name
            category_path = [entry.path]
            full_category_path = f"{name}.{category}"

            # loader, mod_name, is_pkg
            for _, mod_name, _ in pkgutil.walk_packages(category_path, f"{full_category_path}."):
                module = importlib.import_module(mod_name)

                # name, obj
                for _, obj in inspect.getmembers(module, inspect.isclass):
                    # Filter to ensure we only get valid leaf classes:
                    # 1. Must be a subclass of BaseProvider
                    # 2. Must NOT be a BaseProvider class itself (to avoid probe errors)
                    # 3. Must have is_provider set to True (default)
                    if (
                        issubclass(obj, BaseProvider)
                        and obj is not BaseProvider
                        and "BaseApplication" not in obj.__name__
                        and getattr(obj, "is_provider", False)
                    ):
                        yield category, obj


def discover_providers(probe=True, path=None) -> Dict[str, List[BaseProvider]]:
    """
    Recursively discovers and probes providers in subdirectories.
    Returns a dictionary categorized by the subdirectory name.

    Example return:
    {
        "software": [<SpackProvider instance>],
        "workload": [<FluxProvider instance>]
    }
    """
    catalog = {}
    for category, cls in find_provider_classes(path):
        # Wrap in try-except to skip any intermediate logic classes
        # that might have accidentally left is_provider=True
        try:
            instance = cls()
            instance.category = category
            if not probe or instance.probe():
                if category not in catalog:
                    catalog[category] = []
                catalog[category].append(instance)
        except (NotImplementedError, TypeError):
            continue
    return catalog


def get_providers(categories=None, root_path=None) -> Dict[str, List[BaseProvider]]:
    """
    Returns every provider found in the library, regardless of probe status.
    Used for cataloging and documentation.
    """
    catalog = {}
    for category, cls in find_provider_classes(root_path):
        try:
            # Skip over if we don't want it
            if categories and category not in categories:
                continue
            instance = cls()
            instance.category = category
            if category not in catalog:
                catalog[category] = []
            catalog[category].append(instance)
        except (NotImplementedError, TypeError):
            continue

    return catalog
