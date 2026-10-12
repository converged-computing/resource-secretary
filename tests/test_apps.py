"""The application library and its prompt matrices."""

from resource_secretary.apps import discover_applications, get_application, get_applications
from resource_secretary.apps.app import BaseApplication


def test_applications_are_found_by_category():
    apps = get_applications()
    assert "molecular_dynamics" in apps
    assert [a.name for a in apps["molecular_dynamics"]] == ["lammps"]
    assert all(isinstance(a, BaseApplication) for v in apps.values() for a in v)
    discovered = discover_applications()
    assert "app_molecular_dynamics" in discovered and "general" not in discovered
    assert all(k.startswith("app_") for k in discovered)


def test_get_application_is_case_insensitive():
    assert get_application("LAMMPS").name == "lammps"
    assert get_application("nope") is None


def test_lammps_prompt_matrix():
    app = get_application("lammps")
    assert set(app.workloads) >= {"reaxff", "lj"} and "nocite" in app.modifiers
    kwargs = dict(
        workload="reaxff", manager="flux", modifiers=None, flatten=True, nodes=5, tasks=320
    )
    everything = app.get_prompt_matrix(filters="", **kwargs)
    assert everything
    item = everything[0]
    assert set(item) >= {"command", "prompt", "prompt_style", "ground_truth_params"}
    assert all("lmp" in x["command"] for x in everything)
    exact = app.get_prompt_matrix(filters="exact", **kwargs)
    assert 0 < len(exact) <= len(everything)
    assert all("exact" in x["prompt_style"] for x in exact)
    assert app.get_prompt_matrix(filters="no-such-style", **kwargs) == []


def test_lammps_problem_size_validator_is_a_read_only_tool():
    app = get_application("lammps")
    tool = app.validate_lmp_problem_size
    assert tool.is_tool and tool.tool_category == "secretary"
    assert "validate_lmp_problem_size" in app.discover_tools()

    ok = app.validate_lmp_problem_size("lmp -v x 32 -v y 32 -v z 16 -in in.reaxff", 32, 32, 16)
    assert ok["is_valid"] and ok["parsed_dimensions"] == {"x": 32.0, "y": 32.0, "z": 16.0}

    off = app.validate_lmp_problem_size("lmp -v x 32 -v y 8 -in in.reaxff", 32, 32, 16)
    assert not off["is_valid"]
    assert off["missing_dimensions"] == ["z"] and off["mismatched_dimensions"] == ["y"]

    assert not app.validate_lmp_problem_size("", 1, 1, 1)["is_valid"]
    assert not app.validate_lmp_problem_size("lmp -x 32 -y 32 -z 16", 32, 32, 16)["is_valid"]
