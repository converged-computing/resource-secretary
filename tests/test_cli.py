"""The resource-secretary CLI, run as a subprocess so every command is exercised end to end."""

import json
import subprocess
import sys


def run(*args):
    code = "import sys; from resource_secretary.cli.secretary import main; sys.argv = ['resource-secretary'] + sys.argv[1:]; main()"
    result = subprocess.run([sys.executable, "-c", code, *args], capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


def test_help_and_unknown_command():
    code, out = run()
    assert code == 0 and "detect" in out and "providers" in out
    code, out = run("bogus")
    assert code != 0


def test_providers_real_and_simulated():
    code, out = run("providers")
    assert code == 0 and "FLUX" in out and "SLURM" in out and "SPACK" in out
    code, out = run("providers", "--simulated")
    assert code == 0 and "FLUX" in out and "Provider Catalog" in out


def test_apps_and_prompt():
    code, out = run("apps")
    assert code == 0 and "LAMMPS" in out and "reaxff" in out
    code, out = run("prompt", "lammps", "--show-count")
    assert code == 0 and "generated prompts" in out
    code, out = run("prompt", "lammps", "--show-count", "--level", "exact")
    assert code == 0 and "filter: exact" in out
    code, out = run("prompt", "lammps", "-n", "1")
    assert code == 0 and "Truth:" in out and "Prompt:" in out
    code, out = run("prompt", "nope")
    assert code == 1 and "not found" in out


def test_prompt_output_file(tmp_path):
    out_file = tmp_path / "prompts.json"
    code, out = run("prompt", "lammps", "-n", "2", "-o", str(out_file))
    assert code == 0, out
    items = json.load(open(out_file))
    assert len(items) == 2 and {"command", "prompt", "prompt_style"} <= set(items[0])


def test_detect_json_for_one_provider():
    """The generic software provider probes true everywhere."""
    code, out = run("detect", "software", "software", "--json")
    assert code == 0, out
    data = json.loads(out[out.index("{") :])
    assert "software" in data and "software" in data["software"]
    code, out = run("detect", "nosuchcategory")
    assert code == 0 and "not found" in out
