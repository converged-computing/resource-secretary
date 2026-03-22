import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional

from ..provider import BaseProvider, secretary_tool


class KubernetesProvider(BaseProvider):
    """
    Manages interaction with Kubernetes clusters.
    Detects available contexts and provides tools for live cluster investigation.
    """

    def __init__(self):
        super().__init__()
        self.kubectl_path: Optional[str] = None
        self.available: bool = False
        self.active_contexts: List[str] = []

    @property
    def name(self) -> str:
        return "kubernetes"

    def probe(self) -> bool:
        """
        Probes for the kubectl binary and verifies that at least one
        cluster context is defined in the local kubeconfig.

        Returns:
            bool: True if kubectl is found and at least one context exists.
        """
        self.kubectl_path = shutil.which("kubectl")
        if not self.kubectl_path:
            return False

        # Even if the binary exists, we check if any contexts are defined
        # This is an offline check that reads the local config
        contexts_raw = self.run_kubectl(["config", "get-contexts", "-o", "name"])
        if contexts_raw and "error" not in contexts_raw.lower():
            self.active_contexts = contexts_raw.splitlines()
            self.available = len(self.active_contexts) > 0

        return self.available

    def run_kubectl(self, args: List[str]) -> str:
        """
        Executes a kubectl command directly as a subprocess.

        Inputs:
            args (List[str]): List of command arguments (e.g., ['get', 'nodes']).

        Returns:
            str: The stripped stdout of the command execution.
        """
        if not self.kubectl_path:
            return "Error: kubectl binary not found."

        try:
            result = subprocess.run(
                [self.kubectl_path] + args, capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return f"Kubectl Error: {result.stderr.strip()}"
        except Exception as e:
            return f"Subprocess Error: {str(e)}"

    @property
    def metadata(self) -> Dict[str, Any]:
        """
        Returns the current context and the list of all discovered contexts.

        Returns:
            Dict: Includes 'current_context', 'available_contexts' list,
                  and 'bin_path'.
        """
        if not self.available:
            return {"installed": False, "reason": "No contexts found in kubeconfig"}

        current = self.run_kubectl(["config", "current-context"])
        return {
            "current_context": current,
            "available_contexts": self.active_contexts,
            "bin_path": self.kubectl_path,
        }

    @secretary_tool
    def test_cluster_connectivity(self) -> str:
        """
        Performs a live check to see if the current cluster is reachable.

        Returns:
            str: The output of 'kubectl cluster-info'. Use this to verify
                 if the cluster is actually online before proposing a job.
        """
        return self.run_kubectl(["cluster-info"])

    @secretary_tool
    def list_namespaces(self) -> List[str]:
        """
        Lists all namespaces available in the current cluster.

        Returns:
            List[str]: A list of namespace names. Use this to determine
                       where application pods can be deployed.
        """
        output = self.run_kubectl(["get", "namespaces", "-o", "name"])
        if "Error" in output:
            return []
        # Namespaces are returned as namespace/name, we strip the prefix
        return [line.split("/")[-1] for line in output.splitlines()]

    @secretary_tool
    def get_resource_capacity(self) -> str:
        """
        Retrieves the CPU and Memory capacity of all nodes in the cluster.

        Returns:
            str: A table showing node names, status, and resource capacity.
                 Use this to verify if the cluster has the physical
                 resources required for the job.
        """
        return self.run_kubectl(
            [
                "get",
                "nodes",
                "-o",
                "custom-columns=NAME:.metadata.name,STATUS:.status.conditions[-1].type,CPU:.status.capacity.cpu,MEMORY:.status.capacity.memory",
            ]
        )

    @secretary_tool
    def switch_context(self, context_name: str) -> str:
        """
        Switches the active kubectl context to a different cluster.

        Inputs:
            context_name (str): The name of the context to switch to.

        Returns:
            str: Confirmation message of the switch. Use this if a
                 secondary cluster in the config is a better match.
        """
        if context_name not in self.active_contexts:
            return f"Error: Context '{context_name}' not found in available contexts."
        return self.run_kubectl(["config", "use-context", context_name])
