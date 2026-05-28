import csv
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

import resource_secretary.utils as utils

from ..provider import BaseProvider, workflow_tool

# Module-level environment configuration
SNAKEMAKE_WORK_DIR = os.environ.get("RESOURCE_SECRETARY_SNAKEMAKE_WORKDIR")
SNAKEMAKE_INPUT_DIR = os.environ.get("RESOURCE_SECRETARY_SNAKEMAKE_INPUT")
SNAKEMAKE_WRAPPER_VERSION = os.environ.get("RESOURCE_SECRETARY_SNAKEMAKE_WRAPPER_VERSION", "master")
SNAKEMAKE_WRAPPER_CLONE = os.environ.get("RESOURCE_SECRETARY_SNAKEMAKE_WRAPPER_CLONE")
SHARED_EXECUTE_DOCSTRING = """
        Args:
            rule_name (str): A unique snake_case identifier for this rule.
            input (dict): Mapping of input argument names to file paths.
                - Staged files: relative to WORK_DIR/input/ (e.g. "samples/A_1.fastq")
                - Prior step outputs: prefix with 'steps/NN_rulename/'
            output (dict): Mapping of output argument names to file paths.
                - Relative to this step's directory.
            params (dict, optional): Tool parameters.
            threads (int, optional): Threads to allocate.
            cores (int, optional): Cores to allocate.
            log (str, optional): Pass truthy value to enable automatic logging.
"""


def _validate_path(path: str, mode: str = "read") -> tuple[Optional[Path], Optional[str]]:
    """
    Resolves a path and enforces sandbox boundaries.
    Read access: anywhere under WORK_DIR (covers both input/ and steps/).
    Write access: only under WORK_DIR/steps/.
    Returns (Path, None) on success or (None, error_string) on failure.
    """
    if not SNAKEMAKE_WORK_DIR:
        return None, "RESOURCE_SECRETARY_SNAKEMAKE_WORKDIR is not set."

    p = Path(path).resolve()
    work_p = Path(SNAKEMAKE_WORK_DIR).resolve()

    if mode == "write":
        steps_p = work_p / "steps"
        if not p.is_relative_to(steps_p):
            return (
                None,
                f"Security Error: Write access denied. Path '{path}' is outside WORK_DIR/steps/.",
            )
        return p, None

    if mode == "read":
        if p.is_relative_to(work_p):
            return p, None
        return None, f"Security Error: Read access denied. " f"Path '{path}' is outside WORK_DIR."

    return None, "Unknown path error."


def _dir_listing(root: Path) -> List[Dict[str, Any]]:
    """
    Returns a recursive sorted listing of a directory.
    """
    items = []
    for p in sorted(root.rglob("*")):
        items.append(
            {
                "path": str(p.relative_to(root)),
                "type": "dir" if p.is_dir() else "file",
                "size_bytes": p.stat().st_size if p.is_file() else 0,
            }
        )
    return items


class SnakemakeProvider(BaseProvider):
    """
    Workflow catalog provider that exposes snakemake-wrappers as executable
    tools for an agent. On probe, clones the wrappers repository, builds a
    full metadata index, and stages input data into WORK_DIR/input/ via
    symlinks. Provides search, inspection, step-by-step execution, and
    rollback tools. Must be explicitly requested as a catalog because probe
    performs a git clone and filesystem staging.
    """

    is_catalog = True

    def __init__(self, repo_url: str = "https://github.com/snakemake/snakemake-wrappers"):
        super().__init__()
        self.repo_url = repo_url
        self.repo_path: Optional[Path] = None
        self.available: bool = False
        self._index: Dict[str, Dict[str, Any]] = {}
        self._conda_frontend: Optional[str] = None

        # Each entry: {rule_name, step_dir (relative to WORK_DIR), snakefile_bytes}
        self._rules: List[Dict[str, str]] = []
        self._header: str = ""
        self._parallel_mode = False

    @property
    def name(self) -> str:
        return "snakemake"

    @property
    def history(self) -> List[Dict[str, Any]]:
        """
        Generates the history view dynamically from the rules list.
        """
        return [
            {"step": i + 1, "rule_name": r["name"], "step_dir": r["step_dir"]}
            for i, r in enumerate(self._rules)
        ]

    @property
    def _steps_dir(self) -> Path:
        """
        The base directory for all step outputs.
        """
        return Path(SNAKEMAKE_WORK_DIR) / "steps"

    @property
    def snakefile_path(self) -> Path:
        """
        The filesystem location of the Snakefile.
        """
        return Path(SNAKEMAKE_WORK_DIR) / "Snakefile"

    @property
    def metadata(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "wrapper_count": len(self._index),
            "repo_path": str(self.repo_path),
            "wrapper_version": SNAKEMAKE_WRAPPER_VERSION,
            "work_dir": SNAKEMAKE_WORK_DIR,
            "input_dir": SNAKEMAKE_INPUT_DIR,
            "available": self.available,
        }

    def probe(self) -> bool:
        """
        Ensures snakemake and git are installed, clones the wrappers repository
        to a session-scoped temp directory, builds the wrapper index, and stages
        input data into WORK_DIR/input/ via symlinks.
        """
        self._snakemake = shutil.which("snakemake")
        self._git = shutil.which("git")
        conda_bin = shutil.which("mamba") or shutil.which("conda")
        if not (self._snakemake and self._git and conda_bin):
            raise ValueError("Required software (snakemake, git, conda/mamba) not found.")

        self._check_wrapper_utils()
        self._conda_frontend = "mamba" if "mamba" in conda_bin else "conda"
        if not SNAKEMAKE_WORK_DIR:
            raise ValueError("RESOURCE_SECRETARY_SNAKEMAKE_WORKDIR is not set.")

        self.repo_path = self._setup_wrappers()
        self._build_index()
        self._setup_work_dir()
        self.available = True
        return True

    def _setup_wrappers(self):
        """
        Clone the snakemake wrappers
        """
        dest = Path(tempfile.gettempdir()) / "snakemake_wrappers_catalog"
        if SNAKEMAKE_WRAPPER_CLONE and os.path.exists(SNAKEMAKE_WRAPPER_CLONE):
            return Path(SNAKEMAKE_WRAPPER_CLONE)

        if not dest.exists():
            cmd = [self._git, "clone", "--depth", "1", self.repo_url, str(dest)]
        else:
            cmd = [self._git, "-C", str(dest), "pull"]
        subprocess.run(cmd, check=True, capture_output=True)
        return dest

    def _check_wrapper_utils(self):
        """
        Ensures snakemake-wrapper-utils is installed, installing it if not.
        Returns True if available after check, False if install failed.
        """
        try:
            import snakemake_wrapper_utils
        except ImportError:
            raise ValueError(
                "  SnakemakeProvider: snakemake-wrapper-utils not found. Install first."
            )

    def _setup_work_dir(self):
        """
        Creates the canonical WORK_DIR structure and symlinks INPUT_DIR
        contents into WORK_DIR/input/, preserving directory structure.
        """
        work_p = Path(SNAKEMAKE_WORK_DIR)
        for d in ["input", "steps", "logs"]:
            (work_p / d).mkdir(parents=True, exist_ok=True)

        # Create symlinks to actual data, allowing agent to muck with
        if SNAKEMAKE_INPUT_DIR:
            src_root = Path(SNAKEMAKE_INPUT_DIR)
            for src in src_root.rglob("*"):
                rel = src.relative_to(src_root)
                dest = work_p / "input" / rel
                if src.is_dir():
                    dest.mkdir(parents=True, exist_ok=True)
                elif src.is_file() and not dest.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.symlink_to(src.resolve())

    def _build_index(self):
        """
        Walks the cloned wrappers repo and indexes every wrapper found via
        meta.yaml. Collects name, description, authors, conda packages,
        README, and test Snakefile example. Both regular wrappers and
        meta-wrappers are indexed; type field distinguishes them.
        """
        self._index = {}
        for meta_path in self.repo_path.rglob("meta.yaml"):
            wrapper_dir = meta_path.parent
            wrapper_path = str(wrapper_dir.relative_to(self.repo_path))

            # Metadata
            try:
                meta = utils.read_yaml(meta_path) or {}
            except Exception:
                meta = {}

            # Conda environments
            conda_packages = []
            env_path = wrapper_dir / "environment.yaml"
            if env_path.exists():
                try:
                    env = utils.read_yaml(env_path) or {}
                    conda_packages = env.get("dependencies", [])
                except Exception:
                    pass

            # README and example
            readme = ""
            for readme_name in ("README.md", "readme.md"):
                readme_path = wrapper_dir / readme_name
                if readme_path.exists():
                    try:
                        readme = readme_path.read_text()
                        break
                    except Exception:
                        pass

            example_rule = ""
            test_snakefile = wrapper_dir / "test" / "Snakefile"
            if test_snakefile.exists():
                try:
                    example_rule = test_snakefile.read_text()
                except Exception:
                    pass

            wrapper_type = "meta_wrapper" if wrapper_path.startswith("meta/") else "wrapper"
            self._index[wrapper_path] = {
                "path": wrapper_path,
                "category": wrapper_path.split("/")[0],
                "type": wrapper_type,
                "name": meta.get("name", wrapper_path),
                "description": meta.get("description", ""),
                "authors": meta.get("authors", []),
                "conda_packages": conda_packages,
                "readme": readme,
                "example_rule": example_rule,
            }
        print(f"  SnakemakeProvider: indexed {len(self._index)} wrappers.")

    def _rebuild_snakefile(self):
        """
        Assembles the Snakefile from its three components.
        """
        parts = []
        if self._header:
            parts.append(self._header.strip())

        # Target the last rule in the list
        if self._rules:
            last_rule = self._rules[-1]
            target_lines = ["rule all:", "    input:"]

            for path in last_rule["resolved_outputs"]:
                if self._parallel_mode:
                    target_lines.append(f"        expand('{path}', sample=SAMPLES),")
                else:
                    target_lines.append(f"        '{path}',")
            parts.append("\n".join(target_lines))

        for r in self._rules:
            parts.append(r["text"].strip())

        self.snakefile_path.write_text("\n\n".join(parts))

    def _run_snakemake(self, targets: List[str], cores: int = 1) -> subprocess.CompletedProcess:
        """
        Underlying helper to run snakemake with subprocess
        """
        return subprocess.run(
            [
                self._snakemake,
                "--use-conda",
                "--conda-frontend",
                self._conda_frontend,
                "--cores",
                str(cores),
                "--snakefile",
                str(self.snakefile_path),
            ]
            + targets,
            capture_output=True,
            text=True,
            cwd=SNAKEMAKE_WORK_DIR,
        )

    def _apply_path_resolution(self, data: Any, resolver_func) -> Any:
        """
        Recursively traverses dicts/lists to apply a resolution function to path strings.
        """
        if isinstance(data, dict):
            return {k: self._apply_path_resolution(v, resolver_func) for k, v in data.items()}
        if isinstance(data, list):
            return [self._apply_path_resolution(i, resolver_func) for i in data]
        return resolver_func(str(data))

    def _resolve_input_paths(self, input_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Resolve inputs relative to snakemake working directory
        """
        work_p = Path(SNAKEMAKE_WORK_DIR)        
        def input_resolver(item: str):
            if item.startswith("steps/"):
                return str(work_p / item)
            return str(work_p / "input" / item)

        return self._apply_path_resolution(input_data, input_resolver)

    def _resolve_output_paths(self, output: Dict[str, Any], step_dir: Path) -> Dict[str, str]:
        return self._apply_path_resolution(output, lambda item: str(step_dir / item))


    def _add_rule_lines(self, name, resolved, lines):
        """
        shared logic for adding rule lines (input or output)
        """
        lines.append(f"    {name}:")
        if isinstance(resolved, dict):
            for k, v in resolved.items():
                if isinstance(v, list):
                    items = ", ".join(f'"{item}"' for item in v)
                    lines.append(f"        {k}=[{items}],")
                else:
                    lines.append(f'        {k}="{v}",')
        elif isinstance(resolved, list):
            for item in resolved:
                lines.append(f'        "{item}",')
        return lines

    def _build_rule_lines(
        self,
        rule_name: str,
        inputs: Any,
        output: Any,
        params: Optional[Dict[str, Any]],
        threads: int,
        log: Optional[str],
        step_dir: Path,
    ) -> tuple[List[str], Dict[str, str]]:
        """
        Builds the shared input/output/params/threads/log portion of a rule
        with all paths fully resolved. Returns (lines, resolved_output).
        Supports list values for inputs and outputs that expect multiple files.
        """
        # Inputs and outputs
        resolved_input = self._resolve_input_paths(inputs)
        resolved_output = self._resolve_output_paths(output, step_dir)
        lines = [f"rule {rule_name}:"]
        lines = self._add_rule_lines("input", resolved_input, lines)
        lines = self._add_rule_lines("output", resolved_output, lines)

        if params:
            lines.append("    params:")
            for k, v in params.items():
                # This line was giving trouble when the agent asked for tab \t.
                # I think repr (raw) should work
                val = repr(v) if isinstance(v, str) else str(v)
                lines.append(f"        {k}={val},")

        if log:
            log_path = str(Path(SNAKEMAKE_WORK_DIR) / "logs" / f"{rule_name}.log")
            lines.append(f'    log: "{log_path}"')

        lines.append(f"    threads: {threads}")
        return lines, resolved_output

    def _execute(
        self,
        rule_name: str,
        rule_text: str,
        resolved_output: Dict[str, str],
        step_dir: Path,
        cores: int = 1,
    ) -> Dict[str, Any]:
        """
        Structural execution path. Updates state, rebuilds Snakefile, and executes.
        """
        # Path Validation
        all_resolved = []
        for v in resolved_output.values():
            paths = v if isinstance(v, list) else [v]
            for p in paths:
                _, err = _validate_path(p, mode="write")
                if err:
                    return {"success": False, "error": err}
                all_resolved.append(p)

        # Update Internal State
        new_rule = {
            "name": rule_name,
            "text": rule_text,
            "step_dir": str(step_dir.relative_to(SNAKEMAKE_WORK_DIR)),
            "resolved_outputs": all_resolved,
        }
        self._rules.append(new_rule)

        # Prep Disk and Run
        step_dir.mkdir(parents=True, exist_ok=True)
        self._rebuild_snakefile()
        result = self._run_snakemake([], cores=cores)

        # Failure recovery
        if result.returncode != 0:
            self.delete_rule(rule_name)

        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "step_dir": new_rule["step_dir"],
            "work_dir_listing": _dir_listing(Path(SNAKEMAKE_WORK_DIR) / "steps"),
        }

    @workflow_tool
    def create_sample_sheet(self, samples: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Creates a samples.csv file from the provided csv data and automatically
        injects the Python code into the Snakefile to load it. Call this for workflows with
        multiple samples. After discovering data with list_input_dir. The first row MUST be
        the header of the file.

        Args:
            samples (list of dict): A list of dictionaries representing the rows.
                Example: [{"sample": "P19506_1005", "r1": "P19506_1005/R1.fastq", "r2": "P19506_1005/R2.fastq"}]
                Every dictionary must have the exact same keys, and one key MUST be 'sample'
                Paths should be relative to the input directory.

        Returns:
            Instructions on how to use the auto-generated variables (SAMPLES and samples_df)
            in your subsequent execute_rule calls.
        """
        keys = list(samples[0].keys())
        if "sample" not in keys:
            return {"success": False, "error": "The keys must include 'sample'."}

        # Write the csv and add to Snakefile
        out_path = Path(SNAKEMAKE_WORK_DIR) / "input" / "samples.csv"
        try:
            with open(out_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(samples)
        except Exception as e:
            return {"success": False, "error": f"Failed to write CSV: {e}"}

        # This is currently the only thing we write here, so can just set
        self._header = (
            "import pandas as pd\n"
            "samples_df = pd.read_csv('input/samples.csv').set_index('sample', drop=False)\n"
            "SAMPLES = samples_df['sample'].tolist()"
        )
        self._parallel_mode = True
        self._rebuild_snakefile()
        return {"success": True, "message": "Sample sheet created and header updated."}

    @workflow_tool
    def delete_rule(self, rule_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Removes a specific rule from the Snakefile by name.
        If rule_name is None, it removes the most recent rule (Rollback).
        Args:
            rule_name (str): The name of the rule to delete.
        Returns:
            success: True if the rule was found and removed.
        """
        if not self._rules:
            return {"success": False, "error": "No rules exist to remove."}

        # 1. Identify the target rule
        if rule_name:
            target_idx = next(
                (i for i, r in enumerate(self._rules) if r["name"] == rule_name), None
            )
            if target_idx is None:
                return {"success": False, "error": f"Rule '{rule_name}' not found in history."}
            rule_to_remove = self._rules.pop(target_idx)
        else:
            rule_to_remove = self._rules.pop()

        # Filesystem Cleanup
        step_dir_rel = rule_to_remove["step_dir"]
        step_path = (Path(SNAKEMAKE_WORK_DIR) / step_dir_rel).resolve()
        workdir_p = Path(SNAKEMAKE_WORK_DIR).resolve()
        input_p = (workdir_p / "input").resolve()

        # Safety: Ensure we are inside work_dir/steps/ and NOT deleting the root or input
        try:
            if step_path.exists() and step_path.is_relative_to(workdir_p / "steps"):
                if step_path != workdir_p and step_path != input_p:
                    shutil.rmtree(step_path)
        except Exception as e:
            print(f"Warning: Could not delete directory {step_path}: {e}")

        # Synchronize State
        self._rebuild_snakefile()
        return {"success": True, "rule_name": rule_to_remove["name"], "step_dir": step_dir_rel}

    @workflow_tool
    def get_environment(self) -> Dict[str, Any]:
        """
        Returns the agent's runtime environment: the work directory structure,
        path conventions, wrapper version, and current step history. Call this
        first at the start of every session before doing anything else.

        Takes no arguments.

        Returns a dictionary containing:
          - work_dir_structure: description of WORK_DIR layout
          - path_conventions: rules the agent must follow for all file paths
          - wrapper_version: the snakemake-wrappers version in use
          - steps_completed: number of steps executed so far this session
          - history: ordered list of steps executed with their step directories
          - available: whether the provider is ready to use
        """
        return {
            "success": True,
            "work_dir_structure": {
                "input": "WORK_DIR/input/  — staged input data (read-only, do not write here)",
                "steps": "WORK_DIR/steps/  — one subdirectory per executed step (NN_rulename/)",
                "logs": "WORK_DIR/logs/   — per-rule log files written automatically",
                "snakefile": "WORK_DIR/Snakefile — accumulating workflow, appended each step",
            },
            "path_conventions": {
                "input_files": (
                    "Relative to WORK_DIR/input/. "
                    "Example: 'samples/A.fastq' resolves to WORK_DIR/input/samples/A.fastq"
                ),
                "output_files": (
                    "Relative to this step's directory. "
                    "Example: 'A.bam' resolves to WORK_DIR/steps/NN_rulename/A.bam"
                ),
                "chained_inputs": (
                    "To use a prior step's output as input, prefix with 'steps/NN_rulename/'. "
                    "Example: 'steps/01_bwa_mem_A/A.bam'"
                ),
                "never_use": (
                    "Absolute paths, environment variable names, or bare filenames "
                    "without the correct prefix."
                ),
            },
            "wrapper_version": SNAKEMAKE_WRAPPER_VERSION,
            "steps_completed": len(self.history),
            "history": self.history,
            "available": self.available,
        }

    @workflow_tool
    def list_input_dir(self) -> Dict[str, Any]:
        """
        Lists all files staged in WORK_DIR/input/ recursively. Call this
        during Phase 1 (discovery) to understand what input data is available
        before planning the workflow.

        Takes no arguments.

        Returns a dictionary containing:
          - root: the base directory listed ('input/')
          - items: list of dicts with 'path' (relative to input/), 'type'
            (file or dir), and 'size_bytes'. Use these paths directly as
            input values when calling execute_wrapper or execute_rule.
        """
        input_dir = Path(SNAKEMAKE_WORK_DIR) / "input"
        if not input_dir.exists():
            return {"success": False, "error": "Input staging directory does not exist."}

        return {
            "success": True,
            "root": "input/",
            "items": _dir_listing(input_dir),
        }

    @workflow_tool
    def list_work_dir(self) -> Dict[str, Any]:
        """
        Lists all files in WORK_DIR/steps/ recursively, showing what outputs
        have been produced so far. Call this after each execution step to
        verify expected outputs exist before proceeding to the next step.

        Takes no arguments.

        Returns a dictionary containing:
          - root: the base directory listed ('steps/')
          - items: list of dicts with 'path' (relative to steps/), 'type'
            (file or dir), and 'size_bytes'
          - history: ordered list of steps executed this session, each with
            'step' (number), 'rule_name', and 'step_dir'
        """
        if not self.available:
            return {"success": False, "error": "Snakemake provider is not available."}

        steps_dir = Path(SNAKEMAKE_WORK_DIR) / "steps"
        if not steps_dir.exists():
            return {"success": False, "error": "Steps directory does not exist."}

        return {
            "success": True,
            "root": "steps/",
            "items": _dir_listing(steps_dir),
            "history": self.history,
        }

    @workflow_tool
    def search_wrappers(self, query: str) -> Dict[str, Any]:
        """
        Search the snakemake-wrappers catalog by keyword.

        Args:
            query (str): Keyword or phrase to search. Searched across wrapper
                path, name, description, category, and conda package names.
                Examples: 'bwa', 'samtools sort', 'variant calling', 'fastqc'.

        Returns a dictionary containing:
          - count: number of matches found
          - results: list of dicts, each with 'path', 'name', 'type'
            ('wrapper' or 'meta_wrapper'), 'description', and 'category'.
            Use the 'path' value when calling get_wrapper_details or
            execute_wrapper. Call get_wrapper_details on any candidate
            before using it to see full documentation and example rules.
        """
        if not self.available:
            return {"success": False, "error": "Snakemake provider is not available."}

        query_lower = query.lower()
        matches = []
        for wrapper_path, entry in self._index.items():
            searchable = " ".join(
                [
                    entry["path"],
                    entry["name"],
                    entry["description"],
                    entry["category"],
                    entry["type"],
                    " ".join(str(p) for p in entry["conda_packages"]),
                ]
            ).lower()
            if query_lower in searchable:
                matches.append(
                    {
                        "path": entry["path"],
                        "name": entry["name"],
                        "type": entry["type"],
                        "description": entry["description"],
                        "category": entry["category"],
                    }
                )

        return {
            "success": True,
            "count": len(matches),
            "results": matches,
        }

    @workflow_tool
    def get_wrapper_details(self, wrapper_path: str) -> Dict[str, Any]:
        """
        Returns full documentation for a wrapper. You MUST call this before
        execute_wrapper for any wrapper you intend to use.

        Args:
            wrapper_path (str): The catalog path of the wrapper, exactly as
                returned in the 'path' field of search_wrappers results.
                Examples: 'bio/bwa/mem', 'bio/samtools/sort',
                'meta/bio/bwa_mapping'.

        Returns a dictionary containing:
          - name: human-readable wrapper name
          - description: what the wrapper does
          - authors: list of wrapper authors
          - conda_packages: list of software dependencies installed automatically
          - readme: full README text with usage notes
          - example_rule: example Snakefile rule from the wrapper's test suite.
            Inspect this carefully — the input/output key names and params
            shown here are exactly what you must use in execute_wrapper.
          - type: 'wrapper' or 'meta_wrapper'
        """
        if not self.available:
            return {"success": False, "error": "Snakemake provider is not available."}

        entry = self._index.get(wrapper_path)
        if not entry:
            return {"success": False, "error": f"Wrapper '{wrapper_path}' not found in index."}

        return {"success": True, **entry}

    def _next_step_dir(self, rule_name: str) -> Path:
        """
        Returns the next numbered step directory path (not yet created).
        """
        existing_numbers = [0]
        for r in self._rules:
            try:
                # Extract '01' from 'steps/01_rule_name'
                basename = Path(r["step_dir"]).name
                existing_numbers.append(int(basename.split("_")[0]))
            except (ValueError, IndexError):
                pass

        next_num = max(existing_numbers) + 1
        return self._steps_dir / f"{next_num:02d}_{rule_name}"

    @workflow_tool
    def execute_wrapper(
        self,
        rule_name: str,
        wrapper_path: str,
        inputs: Any,
        output: Any,
        params: Optional[Dict[str, Any]] = None,
        threads: int = 1,
        cores: int = 1,
        log: Optional[str] = None,
    ) -> Dict[str, Any]:
        f"""
        Executes a single workflow step using a snakemake-wrappers catalog
        wrapper or meta-wrapper. The rule is appended to the accumulating
        Snakefile and executed immediately. Outputs are written to
        WORK_DIR/steps/NN_rulename/.

        {SHARED_EXECUTE_DOCSTRING}

        Always check 'success' before proceeding to the next step.
        """
        if not self.available:
            return {"success": False, "error": "Snakemake provider is not available."}

        # Strip the version prefix if the agent accidentally included it
        for prefix in [f"{SNAKEMAKE_WRAPPER_VERSION}/", "master/"]:
            if wrapper_path.startswith(prefix):
                wrapper_path = wrapper_path[len(prefix) :]

        entry = self._index.get(wrapper_path)
        if not entry:
            return {"success": False, "error": f"Wrapper '{wrapper_path}' not found in index."}

        # Check against source of truth (self._rules)
        if any(r["name"] == rule_name for r in self._rules):
            return {
                "success": False,
                "error": f"Rule '{rule_name}' already exists. Pick a new name, or use delete_rule('{rule_name}') first.",
            }

        step_dir = self._next_step_dir(rule_name)
        lines, resolved_output = self._build_rule_lines(
            rule_name, inputs, output, params, threads, log, step_dir
        )

        directive = "meta_wrapper" if entry["type"] == "meta_wrapper" else "wrapper"
        lines.append(f'    {directive}: "{SNAKEMAKE_WRAPPER_VERSION}/{wrapper_path}"')
        rule_text = "\n".join(lines)

        return self._execute(rule_name, rule_text, resolved_output, step_dir, cores=cores)

    @workflow_tool
    def execute_rule(
        self,
        rule_name: str,
        inputs: Any,
        output: Any,
        params: Optional[Dict[str, Any]] = None,
        threads: int = 1,
        cores: int = 1,
        log: Optional[str] = None,
        shell: Optional[str] = None,
        run: Optional[str] = None,
        script: Optional[str] = None,
        conda_packages: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        f"""
        Executes a single custom workflow step written by the agent. Use this
        for glue steps that have no suitable catalog wrapper. Exactly one of
        shell, run, or script must be provided. Outputs go to
        WORK_DIR/steps/NN_rulename/.

            shell (str, optional): A shell command string using Snakemake
                placeholder syntax. IMPORTANT: Only binaries available in
                the *system* PATH are accessible here. Bioinformatics tools
                like bwa, samtools, bcftools, and picard are managed by
                wrapper-specific conda environments and are NOT available
                in shell rules. If you need those tools, use execute_wrapper
                instead. Shell rules are only appropriate for standard
                system utilities (cp, mv, ln, awk, python3, etc.).

            run (str, optional): A block of Python code executed directly.
                Has access to the snakemake object for inputs/outputs/params.
                Example: "import shutil\nshutil.copy(snakemake.input[0],
                snakemake.output[0])".
                Exactly one of shell, run, or script must be provided.

            script (str, optional): Path to an external script file relative
                to WORK_DIR. The script receives a snakemake object
                automatically. Exactly one of shell, run, or script must
                be provided.

            conda_packages (list, optional): list of conda package names.

            {SHARED_EXECUTE_DOCSTRING}

        Always check 'success' before proceeding to the next step.
        """
        if not self.available:
            return {"success": False, "error": "Snakemake provider is not available."}

        directives = [x for x in (shell, run, script) if x is not None]
        if len(directives) != 1:
            return {
                "success": False,
                "error": "Exactly one of 'shell', 'run', or 'script' must be provided.",
            }

        # Check against source of truth (self._rules)
        if any(r["name"] == rule_name for r in self._rules):
            return {
                "success": False,
                "error": f"Rule '{rule_name}' already exists. Pick a new name, or use delete_rule('{rule_name}') first.",
            }

        step_dir = self._next_step_dir(rule_name)
        lines, resolved_output = self._build_rule_lines(
            rule_name, inputs, output, params, threads, log, step_dir
        )

        if conda_packages:
            env_yaml_path = self.write_conda_environment(step_dir, conda_packages)
            lines.append(f'    conda: "{env_yaml_path.relative_to(SNAKEMAKE_WORK_DIR)}"')

        if shell is not None:
            lines.append(f'    shell: "{shell}"')
        elif script is not None:
            lines.append(f'    script: "{script}"')
        elif run is not None:
            lines.append("    run:")
            for line in run.splitlines():
                lines.append(f"        {line}")

        rule_text = "\n".join(lines)
        return self._execute(rule_name, rule_text, resolved_output, step_dir, cores=cores)

    @workflow_tool
    def view_snakefile(self) -> Dict[str, Any]:
        """
        Returns the full content of the current Snakefile.
        Use this to inspect the sequence of rules and their parameters.

        Returns a dictionary containing:
          - success (bool): True if file was read
          - content (str): The full text of the Snakefile
          - rule_count (int): Number of rules currently defined
        """
        if not self.snakefile_path.exists():
            return {"success": True, "content": "", "rule_count": 0}

        try:
            content = self.snakefile_path.read_text()
            # Basic count by looking for the "rule " keyword at the start of lines
            rule_count = len(
                [line for line in content.splitlines() if line.strip().startswith("rule ")]
            )
            return {"success": True, "content": content, "rule_count": rule_count}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def write_conda_environment(self, step_dir, packages):
        """
        Write one or more conda packages to a step directory.
        """
        step_dir.mkdir(parents=True, exist_ok=True)
        path = step_dir / "env.yaml"
        env_content = {
            "channels": ["conda-forge", "bioconda", "nodefaults"],
            "dependencies": packages,
        }
        utils.write_yaml(env_content, path)
        return path

    def rule_exists(self, step_dir, rule_name):
        """
        Shared function to determine if a rule exists.
        """
        existing_rule_names = [h["rule_name"] for h in self.history]
        return rule_name in existing_rule_names or step_dir.exists()

    def rollback_step(self) -> Dict[str, Any]:
        """
        Rolls back the most recently executed step. Removes the step's output
        directory from WORK_DIR/steps/, truncates the Snakefile to remove the
        appended rule, and pops the step from history.
        """
        return self.delete_rule(None)
