import os

from resource_secretary.providers import find_provider_classes, get_providers


def get_applications():
    """
    Get all applications
    """
    path = os.path.dirname(__file__)
    return get_providers(root_path=path)


def discover_applications():
    """
    Analogous to discover_providers, but add prefix. Leave out general.
    """
    apps = {}
    for name, app in get_applications().items():
        if name == "general":
            continue
        # This should prevent any potential namespace conflicts.
        apps[f"app_{name}"] = app
    return apps


def get_application(name):
    """
    Finds an application by name and returns an instance.
    """
    path = os.path.dirname(__file__)
    for _, cls in find_provider_classes(path):
        # Check class name or name property
        inst = cls()
        if inst.name.lower() == name.lower():
            return inst
    return None
