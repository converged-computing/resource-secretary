import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from ..provider import BaseProvider, workflow_tool

# Module-level environment configuration, read at import time
SNAKEMAKE_WORK_DIR = os.environ.get("RESOURCE_SECRETARY_SNAKEMAKE_WORKDIR")
SNAKEMAKE_INPUT_DIR = os.environ.get("RESOURCE_SECRETARY_SNAKEMAKE_INPUT")
SNAKEMAKE_WRAPPER_VERSION = os.environ.get("RESOURCE_SECRETARY_SNAKEMAKE_WRAPPER_VERSION", "master")
SNAKEMAKE_WRAPPER_CLONE = os.environ.get("RESOURCE_SECRETARY_SNAKEMAKE_WRAPPER_CLONE")

print(f"  SNAKEMAKE_WORK_DIR:        {SNAKEMAKE_WORK_DIR}")
print(f"  SNAKEMAKE_INPUT_DIR:       {SNAKEMAKE_INPUT_DIR}")
print(f"  SNAKEMAKE_WRAPPER_VERSION: {SNAKEMAKE_WRAPPER_VERSION}")


def _validate_path(path: str, mode: str = "read") -> tuple[Optional[Path], Optional[str]]:
    """
    Resolves a path and enforces sandbox boundaries.
    Read access: anywhere under WORK_DIR (covers both input/ and steps/).
    Write access: only under WORK_DIR/steps/.
    Returns (Path, None) on success or (None, error_string) on failure.
    """
    if not SNAKEMAKE_WORK_DIR:
        return None, "RESOURCE_SECRETARY_SNAKEMAKE_WORKDIR is not set."

    try:
        p = Path(path).resolve()
        work_p = Path(SNAKEMAKE_WORK_DIR).resolve()

        if mode == "write":
            steps_p = work_p / "steps"
            if not p.is_relative_to(steps_p):
                return None, (
                    f"Security Error: Write access denied. "
                    f"Path '{path}' is outside WORK_DIR/steps/."
                )
            return p, None

        if mode == "read":
            if p.is_relative_to(work_p):
                return p, None
            return None, (
                f"Security Error: Read access denied. " f"Path '{path}' is outside WORK_DIR."
            )

    except Exception as e:
        return None, f"Path resolution error: {e}"

    return None, "Unknown path error."


def _dir_listing(root: Path) -> List[Dict[str, Any]]:
    """Returns a recursive sorted listing of a directory."""
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

        # Execution state
        self._history = []
        # Each entry: {rule_name, step_dir (relative to WORK_DIR), snakefile_bytes}

    @property
    def name(self) -> str:
        return "snakemake"

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
            "steps_completed": len(self._history),
        }

    def probe(self) -> bool:
        """
        Ensures snakemake and git are installed, clones the wrappers repository
        to a session-scoped temp directory, builds the wrapper index, and stages
        input data into WORK_DIR/input/ via symlinks.
        """
        if not shutil.which("snakemake"):
            raise ValueError("  SnakemakeProvider: snakemake not found in PATH.")
        if not shutil.which("git"):
            raise ValueError("  SnakemakeProvider: git not found in PATH.")
        if not SNAKEMAKE_WORK_DIR:
            raise ValueError(
                "  SnakemakeProvider: RESOURCE_SECRETARY_SNAKEMAKE_WORKDIR is not set."
            )
        if not shutil.which("mamba") and not shutil.which("conda"):
            raise ValueError(
                "  SnakemakeProvider: neither mamba nor conda found in PATH. One is required for --use-conda wrapper execution."
            )
        self._check_wrapper_utils()
        self._conda_frontend = "mamba" if shutil.which("mamba") else "conda"

        if SNAKEMAKE_WRAPPER_CLONE is not None and os.path.exists(SNAKEMAKE_WRAPPER_CLONE):
            self.repo_url = SNAKEMAKE_WRAPPER_CLONE
        else:
            self.repo_path = self.clone_snakemake()

        self._build_index()
        self._setup_work_dir()
        self.available = True
        return self.available

    def clone_snakemake(self):
        """
        Clone snakemake to a temporary directory
        """
        tmp_dir = Path(tempfile.gettempdir()) / "snakemake_wrappers_catalog"
        if not tmp_dir.exists():
            print(f"  SnakemakeProvider: cloning wrappers to {tmp_dir} ...")
            subprocess.run(
                ["git", "clone", "--depth", "1", self.repo_url, str(tmp_dir)],
                check=True,
                capture_output=True,
            )
        else:
            print(f"  SnakemakeProvider: wrappers repo exists at {tmp_dir}, pulling latest.")
            subprocess.run(
                ["git", "-C", str(tmp_dir), "pull"],
                capture_output=True,
            )
        return tmp_dir

    def _check_wrapper_utils(self) -> bool:
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
        input_stage = work_p / "input"
        steps_dir = work_p / "steps"
        logs_dir = work_p / "logs"

        for d in (work_p, input_stage, steps_dir, logs_dir):
            d.mkdir(parents=True, exist_ok=True)

        # Symlink INPUT_DIR contents into input/ preserving structure
        if SNAKEMAKE_INPUT_DIR:
            input_src = Path(SNAKEMAKE_INPUT_DIR)
            for src in sorted(input_src.rglob("*")):
                rel = src.relative_to(input_src)
                dest = input_stage / rel
                if src.is_dir():
                    dest.mkdir(parents=True, exist_ok=True)
                elif src.is_file() and not dest.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.symlink_to(src.resolve())

        print(f"  SnakemakeProvider: work dir staged at {work_p}")

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

            try:
                with open(meta_path) as f:
                    meta = yaml.safe_load(f) or {}
            except Exception:
                continue

            conda_packages = []
            env_path = wrapper_dir / "environment.yaml"
            if env_path.exists():
                try:
                    with open(env_path) as f:
                        env = yaml.safe_load(f) or {}
                    conda_packages = env.get("dependencies", [])
                except Exception:
                    pass

            readme = ""
            for readme_name in ("README.md", "readme.md"):
                readme_path = wrapper_dir / readme_name
                if readme_path.exists():
                    try:
                        readme = readme_path.read_text()
                    except Exception:
                        pass
                    break

            example_rule = ""
            test_snakefile = wrapper_dir / "test" / "Snakefile"
            if test_snakefile.exists():
                try:
                    example_rule = test_snakefile.read_text()
                except Exception:
                    pass

            category = wrapper_path.split("/")[0]
            wrapper_type = "meta_wrapper" if wrapper_path.startswith("meta/") else "wrapper"

            self._index[wrapper_path] = {
                "path": wrapper_path,
                "category": category,
                "type": wrapper_type,
                "name": meta.get("name", wrapper_path),
                "description": meta.get("description", ""),
                "authors": meta.get("authors", []),
                "conda_packages": conda_packages,
                "readme": readme,
                "example_rule": example_rule,
            }

        print(f"  SnakemakeProvider: indexed {len(self._index)} wrappers.")

    @property
    def _snakefile_path(self) -> Path:
        return Path(SNAKEMAKE_WORK_DIR) / "Snakefile"

    @property
    def _steps_dir(self) -> Path:
        return Path(SNAKEMAKE_WORK_DIR) / "steps"

    def _next_step_dir(self, rule_name: str) -> Path:
        """Returns the next numbered step directory path (not yet created)."""
        n = len(self._history) + 1
        return self._steps_dir / f"{n:02d}_{rule_name}"

    def _append_rule(self, rule_text: str):
        """Appends a rule block to the accumulating Snakefile."""
        with open(self._snakefile_path, "a") as f:
            f.write("\n\n")
            f.write(rule_text)

    def _snakefile_size(self) -> int:
        """Returns current Snakefile byte length, 0 if not yet created."""
        if self._snakefile_path.exists():
            return self._snakefile_path.stat().st_size
        return 0

    def _run_snakemake(self, targets: List[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                "snakemake",
                "--use-conda",
                "--conda-frontend",
                self._conda_frontend,
                "--cores",
                "1",
                "--snakefile",
                str(self._snakefile_path),
            ]
            + targets,
            capture_output=True,
            text=True,
            cwd=SNAKEMAKE_WORK_DIR,
        )

    def _resolve_input_paths(self, input: Dict[str, Any]) -> Dict[str, str]:
        """
        Resolves input paths relative to WORK_DIR.
        Paths starting with 'steps/' are resolved relative to WORK_DIR.
        All other paths are assumed relative to WORK_DIR/input/.
        Supports list values for inputs that expect multiple files (e.g. index sets).
        """
        resolved = {}
        work_p = Path(SNAKEMAKE_WORK_DIR)
        for k, v in input.items():
            if isinstance(v, list):
                resolved_list = []
                for item in v:
                    item = str(item)
                    if item.startswith("steps/"):
                        resolved_list.append(str(work_p / item))
                    else:
                        resolved_list.append(str(work_p / "input" / item))
                resolved[k] = resolved_list
            else:
                v = str(v)
                if v.startswith("steps/"):
                    resolved[k] = str(work_p / v)
                else:
                    resolved[k] = str(work_p / "input" / v)
        return resolved

    def _resolve_output_paths(self, output: Dict[str, Any], step_dir: Path) -> Dict[str, str]:
        """
        Resolves output paths relative to the step's output directory.
        Supports list values for outputs that produce multiple files.
        """
        resolved = {}
        for k, v in output.items():
            if isinstance(v, list):
                resolved[k] = [str(step_dir / str(item)) for item in v]
            else:
                resolved[k] = str(step_dir / str(v))
        return resolved

    def _build_rule_lines(
        self,
        rule_name: str,
        input: Dict[str, Any],
        output: Dict[str, Any],
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
        resolved_input = self._resolve_input_paths(input)
        resolved_output = self._resolve_output_paths(output, step_dir)

        lines = [f"rule {rule_name}:"]

        lines.append("    input:")
        for k, v in resolved_input.items():
            if isinstance(v, list):
                items = ", ".join(f'"{item}"' for item in v)
                lines.append(f"        {k}=[{items}],")
            else:
                lines.append(f'        {k}="{v}",')

        lines.append("    output:")
        for k, v in resolved_output.items():
            if isinstance(v, list):
                items = ", ".join(f'"{item}"' for item in v)
                lines.append(f"        {k}=[{items}],")
            else:
                lines.append(f'        {k}="{v}",')

        if params:
            lines.append("    params:")
            for k, v in params.items():
                val = f'"{v}"' if isinstance(v, str) else str(v)
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
    ) -> Dict[str, Any]:
        """
        Shared execution path for both execute_wrapper and execute_rule.
        """
        # Auto-rollback if this rule_name or step_dir already exists
        existing_rule_names = [h["rule_name"] for h in self._history]
        if rule_name in existing_rule_names or step_dir.exists():
            rollback_result = self.rollback_step()
            if not rollback_result["success"]:
                return {
                    "success": False,
                    "error": (
                        f"Rule '{rule_name}' already exists and auto-rollback failed: "
                        f"{rollback_result.get('error')}"
                    ),
                }
            # Recalculate step_dir after rollback since history length changed
            step_dir = self._next_step_dir(rule_name)

        # Validate all resolved output paths
        for v in resolved_output.values():
            _, err = _validate_path(v, mode="write")
            if err:
                return {"success": False, "error": err}

        pre_append_size = self._snakefile_size()
        step_dir.mkdir(parents=True, exist_ok=True)
        self._append_rule(rule_text)
        self._history.append(
            {
                "rule_name": rule_name,
                "step_dir": str(step_dir.relative_to(SNAKEMAKE_WORK_DIR)),
                "snakefile_bytes": pre_append_size,
            }
        )

        targets = list(resolved_output.values())
        result = self._run_snakemake(targets)

        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "auto_rolled_back": rule_name in existing_rule_names or step_dir.exists(),
            "step_dir": str(step_dir.relative_to(SNAKEMAKE_WORK_DIR)),
            "work_dir_listing": _dir_listing(Path(SNAKEMAKE_WORK_DIR) / "steps"),
        }

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
            "steps_completed": len(self._history),
            "history": [
                {"step": i + 1, "rule_name": h["rule_name"], "step_dir": h["step_dir"]}
                for i, h in enumerate(self._history)
            ],
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
            "history": [
                {"step": i + 1, "rule_name": h["rule_name"], "step_dir": h["step_dir"]}
                for i, h in enumerate(self._history)
            ],
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

    @workflow_tool
    def execute_wrapper(
        self,
        rule_name: str,
        wrapper_path: str,
        input: Dict[str, Any],
        output: Dict[str, Any],
        params: Optional[Dict[str, Any]] = None,
        threads: int = 1,
        log: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes a single workflow step using a snakemake-wrappers catalog
        wrapper or meta-wrapper. The rule is appended to the accumulating
        Snakefile and executed immediately. Outputs are written to
        WORK_DIR/steps/NN_rulename/.

        Args:
            rule_name (str): A unique snake_case identifier for this rule.
                Must be a valid Python identifier. Used to name the step
                directory (WORK_DIR/steps/NN_rulename/). Examples:
                'bwa_mem_A', 'samtools_sort_sample_B'.

            wrapper_path (str): Catalog path of the wrapper exactly as
                returned by search_wrappers. Examples: 'bio/bwa/mem',
                'bio/samtools/sort', 'meta/bio/bwa_mapping'.

            input (dict): Mapping of input argument names to file paths.
                Key names MUST match those shown in the wrapper's example
                rule (from get_wrapper_details). Path conventions:
                  - Staged input files: relative to WORK_DIR/input/.
                    Example: {"reads": "samples/A.fastq", "ref": "genome.fa"}
                  - Prior step outputs: prefix with 'steps/NN_rulename/'.
                    Example: {"bam": "steps/01_bwa_mem_A/A.bam"}
                Never use absolute paths or environment variable names.

            output (dict): Mapping of output argument names to file paths.
                Key names MUST match those shown in the wrapper's example
                rule. Paths are relative to this step's directory
                (WORK_DIR/steps/NN_rulename/).
                Example: {"bam": "A.bam"} writes to
                WORK_DIR/steps/NN_rulename/A.bam.
                Never use absolute paths or environment variable names.

            params (dict, optional): Mapping of parameter names to values
                as shown in the wrapper's example rule. Values can be
                strings, integers, or booleans.
                Example: {"sorting": "samtools", "sort_order": "coordinate"}.

            threads (int, optional): Number of threads to allocate.
                Defaults to 1.

            log (str, optional): Pass any truthy value to enable logging.
                Log written automatically to WORK_DIR/logs/{rule_name}.log.

        Returns a dictionary containing:
          - success (bool): True if snakemake exited with returncode 0
          - returncode (int): snakemake process return code
          - stdout (str): snakemake standard output
          - stderr (str): snakemake standard error — inspect this carefully
            on failure to understand what went wrong
          - step_dir (str): path of this step's output directory relative
            to WORK_DIR, e.g. 'steps/01_bwa_mem_A'
          - work_dir_listing: current recursive listing of WORK_DIR/steps/

        Always check 'success' before proceeding to the next step.
        Use rollback_step to undo this step if you want to retry with
        different arguments.
        """
        if not self.available:
            return {"success": False, "error": "Snakemake provider is not available."}

        entry = self._index.get(wrapper_path)
        if not entry:
            return {"success": False, "error": f"Wrapper '{wrapper_path}' not found in index."}

        step_dir = self._next_step_dir(rule_name)
        lines, resolved_output = self._build_rule_lines(
            rule_name, input, output, params, threads, log, step_dir
        )
        directive = "meta_wrapper" if entry["type"] == "meta_wrapper" else "wrapper"
        lines.append(f'    {directive}: "{SNAKEMAKE_WRAPPER_VERSION}/{wrapper_path}"')
        rule_text = "\n".join(lines)

        return self._execute(rule_name, rule_text, resolved_output, step_dir)

    @workflow_tool
    def execute_rule(
        self,
        rule_name: str,
        input: Dict[str, Any],
        output: Dict[str, Any],
        params: Optional[Dict[str, Any]] = None,
        threads: int = 1,
        log: Optional[str] = None,
        shell: Optional[str] = None,
        run: Optional[str] = None,
        script: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes a single custom workflow step written by the agent. Use this
        for glue steps that have no suitable catalog wrapper. Exactly one of
        shell, run, or script must be provided. Outputs go to
        WORK_DIR/steps/NN_rulename/.

        Args:
            rule_name (str): A unique snake_case identifier for this rule.
                Must be a valid Python identifier. Used to name the step
                directory (WORK_DIR/steps/NN_rulename/). Examples:
                'convert_sam_to_bam', 'rename_output_A'.

            input (dict): Mapping of input argument names to file paths.
                Path conventions:
                  - Staged input files: relative to WORK_DIR/input/.
                    Example: {"reads": "samples/A.fastq"}
                  - Prior step outputs: prefix with 'steps/NN_rulename/'.
                    Example: {"bam": "steps/01_bwa_mem_A/A.bam"}
                Never use absolute paths or environment variable names.

            output (dict): Mapping of output argument names to file paths.
                Paths are relative to this step's directory
                (WORK_DIR/steps/NN_rulename/).
                Example: {"sorted": "A.sorted.bam"} writes to
                WORK_DIR/steps/NN_rulename/A.sorted.bam.
                Never use absolute paths or environment variable names.

            params (dict, optional): Mapping of parameter names to values.
                Accessible in shell commands as {params.key_name}.
                Example: {"min_mapq": 20}.

            threads (int, optional): Number of threads to allocate.
                Defaults to 1.

            log (str, optional): Pass any truthy value to enable logging.
                Log written automatically to WORK_DIR/logs/{rule_name}.log.

            shell (str, optional): A shell command string using Snakemake
                placeholder syntax to reference inputs, outputs, and params.
                Example: "bwa mem {input.ref} {input.reads} | samtools view
                -Sb - > {output.bam}".
                Exactly one of shell, run, or script must be provided.

            run (str, optional): A block of Python code executed directly.
                Has access to the snakemake object for inputs/outputs/params.
                Example: "import shutil\nshutil.copy(snakemake.input[0],
                snakemake.output[0])".
                Exactly one of shell, run, or script must be provided.

            script (str, optional): Path to an external script file relative
                to WORK_DIR. The script receives a snakemake object
                automatically. Exactly one of shell, run, or script must
                be provided.

        Returns a dictionary containing:
          - success (bool): True if snakemake exited with returncode 0
          - returncode (int): snakemake process return code
          - stdout (str): snakemake standard output
          - stderr (str): snakemake standard error — inspect this carefully
            on failure to understand what went wrong
          - step_dir (str): path of this step's output directory relative
            to WORK_DIR, e.g. 'steps/02_samtools_sort_A'
          - work_dir_listing: current recursive listing of WORK_DIR/steps/

        Always check 'success' before proceeding to the next step.
        Use rollback_step to undo this step if you want to retry with
        different arguments.
        """
        if not self.available:
            return {"success": False, "error": "Snakemake provider is not available."}

        directives = [x for x in (shell, run, script) if x is not None]
        if len(directives) != 1:
            return {
                "success": False,
                "error": "Exactly one of 'shell', 'run', or 'script' must be provided.",
            }

        step_dir = self._next_step_dir(rule_name)
        lines, resolved_output = self._build_rule_lines(
            rule_name, input, output, params, threads, log, step_dir
        )

        if shell is not None:
            lines.append(f'    shell: "{shell}"')
        elif script is not None:
            lines.append(f'    script: "{script}"')
        elif run is not None:
            lines.append("    run:")
            for line in run.splitlines():
                lines.append(f"        {line}")

        rule_text = "\n".join(lines)
        return self._execute(rule_name, rule_text, resolved_output, step_dir)

    @workflow_tool
    def rollback_step(self) -> Dict[str, Any]:
        """
        Rolls back the most recently executed step. Removes the step's output
        directory from WORK_DIR/steps/, truncates the Snakefile to remove the
        appended rule, and pops the step from history.

        Takes no arguments. Always rolls back exactly one step (the most recent).

        Use this when a step has failed and you want to try a different wrapper,
        different parameters, or a custom rule instead. After rolling back, the
        next call to execute_wrapper or execute_rule will reuse the same step
        number.

        Returns a dictionary containing:
          - success (bool): True if rollback completed successfully
          - rolled_back (str): rule_name of the step that was removed
          - step_dir_removed (str): the step directory that was deleted,
            relative to WORK_DIR
          - snakefile_truncated_to_bytes (int): Snakefile size after truncation
          - steps_remaining (int): number of steps still in history
          - history: updated ordered list of remaining steps
        """
        if not self.available:
            return {"success": False, "error": "Snakemake provider is not available."}

        if not self._history:
            return {"success": False, "error": "No steps to roll back."}

        entry = self._history.pop()
        rule_name = entry["rule_name"]
        step_dir = Path(SNAKEMAKE_WORK_DIR) / entry["step_dir"]
        pre_size = entry["snakefile_bytes"]

        # Remove step output directory
        if step_dir.exists():
            shutil.rmtree(step_dir)

        # Truncate Snakefile back to pre-append size
        if self._snakefile_path.exists():
            with open(self._snakefile_path, "r+") as f:
                f.truncate(pre_size)

        return {
            "success": True,
            "rolled_back": rule_name,
            "step_dir_removed": str(entry["step_dir"]),
            "snakefile_truncated_to_bytes": pre_size,
            "steps_remaining": len(self._history),
            "history": [
                {"step": i + 1, "rule_name": h["rule_name"], "step_dir": h["step_dir"]}
                for i, h in enumerate(self._history)
            ],
        }
