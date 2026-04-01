import importlib
import inspect
import os
import pkgutil
import re
from typing import Dict, List

from .provider import BaseProvider


def find_provider_classes():
    """
    Public generator that walks the provider tree and yields categories and classes
    that are marked with is_provider=True.
    """
    pkg_path = os.path.dirname(__file__)
    for entry in os.scandir(pkg_path):
        # Don't include hidden or mock
        if entry.is_dir() and not re.search("(__|mock)", entry.name):
            category = entry.name
            category_path = [entry.path]
            full_category_path = f"{__name__}.{category}"

            # loader, mod_name, is_pkg
            for _, mod_name, _ in pkgutil.walk_packages(category_path, f"{full_category_path}."):
                module = importlib.import_module(mod_name)

                # name, obj
                for _, obj in inspect.getmembers(module, inspect.isclass):
                    # Filter to ensure we only get valid leaf classes:
                    # 1. Must be a subclass of BaseProvider
                    # 2. Must NOT be the BaseProvider class itself (to avoid probe errors)
                    # 3. Must have is_provider set to True (default)
                    if (
                        issubclass(obj, BaseProvider)
                        and obj is not BaseProvider
                        and getattr(obj, "is_provider", False)
                    ):
                        yield category, obj


def discover_providers() -> Dict[str, List[BaseProvider]]:
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
    names = {}
    for category, cls in find_provider_classes():
        # Wrap in try-except to skip any intermediate logic classes
        # that might have accidentally left is_provider=True
        try:
            instance = cls()
            instance.category = category
            if instance.probe():
                if category not in catalog:
                    catalog[category] = []
                catalog[category].append(instance)
        except (NotImplementedError, TypeError):
            continue
    return catalog


def get_all_providers() -> Dict[str, List[BaseProvider]]:
    """
    Returns every provider found in the library, regardless of probe status.
    Used for cataloging and documentation.
    """
    catalog = {}
    for category, cls in find_provider_classes():
        try:
            instance = cls()
            instance.category = category
            if category not in catalog:
                catalog[category] = []
            catalog[category].append(instance)
        except (NotImplementedError, TypeError):
            continue

    return catalog
