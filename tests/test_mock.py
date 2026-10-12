"""Simulated providers: discovery is deterministic per worker id and honors archetypes."""

import subprocess
import sys

import pytest

from resource_secretary.providers.mock import (
    archetypes,
    discover_mock_providers,
    get_mock_providers,
    select_archetype,
)
from resource_secretary.providers.mock.base import MockBaseProvider


def names(catalog):
    return {c: sorted(p.name for p in v) for c, v in catalog.items()}


def test_get_mock_providers_lists_every_category():
    catalog = get_mock_providers()
    assert {
        "workload",
        "software",
        "container",
        "storage",
        "network",
        "hardware",
        "parallel",
    } <= set(catalog)
    for category, instances in catalog.items():
        for inst in instances:
            assert isinstance(inst, MockBaseProvider) and inst.config is not None
    assert set(get_mock_providers(categories=["network"])) == {"network"}


def test_discovery_is_deterministic_for_a_worker_id():
    first = names(discover_mock_providers("worker-1"))
    assert first and first == names(discover_mock_providers("worker-1"))
    assert (
        first != names(discover_mock_providers("worker-2"))
        or names(discover_mock_providers("worker-3")) != first
    )


def test_discovery_is_deterministic_across_processes():
    """hash(str) is salted per process, so the seed must not come from it."""
    code = (
        "from resource_secretary.providers.mock import discover_mock_providers as d;"
        "print(sorted((c, sorted(p.name for p in v)) for c, v in d('worker-1').items()))"
    )
    runs = {
        subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, check=True
        ).stdout.strip()
        for _ in range(3)
    }
    assert len(runs) == 1, runs


def test_explicit_archetype_respects_its_slots():
    for name, cls in archetypes.items():
        catalog = discover_mock_providers("w", choice=name)
        slots = cls().slots
        for category, instances in catalog.items():
            assert category in slots
            assert slots[category]["min"] <= len(instances) <= slots[category]["max"]
            allowed = set(slots[category]["choices"])
            assert all(type(p).__name__ in allowed for p in instances)


def test_select_archetype():
    assert select_archetype(1, choice="HPC") == "hpc"
    assert select_archetype(1) in archetypes
    assert select_archetype(1) == select_archetype(1)
    with pytest.raises(ValueError):
        select_archetype(1, choice="mainframe")


def test_mock_generate_stays_in_archetype_range():
    for category, instances in get_mock_providers().items():
        for inst in instances:
            for key, (lo, hi) in inst.config.archetype.ranges.items():
                value = inst.generate(key)
                assert lo <= value <= hi, (inst.name, key, value)
