"""Provider discovery and the tool decorators. No model, no system probing."""

from typing import Annotated

from resource_secretary.providers import discover_providers, find_provider_classes, get_providers
from resource_secretary.providers.provider import BaseProvider, _base_tool_decorator, secretary_tool

CATEGORIES = {"container", "hardware", "network", "parallel", "software", "storage", "workload"}


class FakeProvider(BaseProvider):
    """A provider with one tool of each category and one plain method."""

    @property
    def name(self):
        return "fake"

    def probe(self):
        return True

    @secretary_tool
    def look(self, path: Annotated[str, "where to look"], depth: int = 1):
        """Look at something."""
        return {"path": path, "depth": depth}

    def act(self, count: int):
        """Act on something, in a category the secretary never asks for."""
        return count * 2

    act = _base_tool_decorator(act, "other")

    def helper(self):
        return "not a tool"


def test_find_provider_classes_covers_every_category_and_skips_bases():
    found = {}
    for category, cls in find_provider_classes():
        found.setdefault(category, []).append(cls)
    assert set(found) == CATEGORIES
    for classes in found.values():
        for cls in classes:
            assert issubclass(cls, BaseProvider) and cls is not BaseProvider
            assert getattr(cls, "is_provider", False)
            assert "BaseApplication" not in cls.__name__
    assert "mock" not in found


def test_get_providers_without_probing_lists_known_names_and_filters():
    catalog = get_providers()
    assert set(catalog) == CATEGORIES
    names = {p.name for p in catalog["workload"]}
    assert {"flux", "slurm", "kubernetes", "pbs"} <= names
    for category, instances in catalog.items():
        assert all(p.category == category for p in instances)
    only = get_providers(categories=["software"])
    assert set(only) == {"software"}


def test_discover_providers_probe_false_matches_get_providers():
    unprobed = discover_providers(probe=False)
    assert {c: sorted(p.name for p in v) for c, v in unprobed.items()} == {
        c: sorted(p.name for p in v) for c, v in get_providers().items()
    }


def test_tool_decorator_records_manifest():
    look = FakeProvider.look
    assert look.is_tool and look.tool_category == "secretary" and look.tool_name == "look"
    assert look.tool_doc == "Look at something."
    assert look.tool_args == {
        "path": {"type": "str", "required": True},
        "depth": {"type": "int", "required": False},
    }
    assert FakeProvider.act.tool_category == "other"
    assert not hasattr(FakeProvider.helper, "is_tool")
    # the wrapper still calls through
    assert FakeProvider().look("/x") == {"path": "/x", "depth": 1}


def test_discover_tools_filters_by_category_and_caches_handlers():
    p = FakeProvider()
    assert set(p.discover_tools()) == {"look"}, "the default is the read-only secretary set"
    both = p.discover_tools(["secretary", "other"])
    assert set(both) == {"look", "act"}
    assert both["look"]["category"] == "secretary" and both["act"]["category"] == "other"
    assert both["look"]["parameters"] == FakeProvider.look.tool_args
    assert both["look"]["handler"]("/y", depth=2) == {"path": "/y", "depth": 2}
    assert p.tools["act"](3) == 6
    assert set(p.discover_tools(["secretary"])) == {"look"}
    assert set(p.discover_tools(["other"])) == {"act"}
    assert p.discover_tools(["nope"]) == {}


def test_base_provider_defaults():
    p = FakeProvider()
    assert p.metadata == {} and p.get_prompt_vocabulary() == {}
    assert p.category == "unknown" and p.is_provider
