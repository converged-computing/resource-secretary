from typing import Any, Dict

from ..provider import BaseProvider, secretary_tool


class FluxProvider(BaseProvider):
    """
    The Flux provider interacts with the Flux Framework using native Python bindings.
    It provides modular tools for deep investigation of scheduler state,
    resource utilization, and queue parameters. Submitting, monitoring and
    cancelling jobs is flux-secretary's job, not the resource secretary's.
    """

    def __init__(self):
        super().__init__()
        self.available: bool = False
        self.handle = None

    @property
    def name(self) -> str:
        return "flux"

    def probe(self) -> bool:
        """
        Checks for the presence of the 'flux' Python library and an active session.
        Sets the public self.handle if successful.

        Returns:
            bool: True if the flux library is importable and a handle can be created.
        """
        try:
            import flux

            # Attempt to create a handle to verify the session is active
            self.handle = flux.Flux()
            self.available = True
        except (ImportError, RuntimeError, Exception):
            self.available = False
        return self.available

    def get_modifier_templates(self):
        """
        Flux-specific flags that can be used in prompts.
        """

    def get_prompt_vocabulary(self):
        """
        Returns Flux-specific templates for the prompt generator.
        """
        return {
            "manager": {
                "exact": "flux run",
                "verbatim": "using flux run",
                "descriptive": "using the Flux workload manager",
                "agnostic": "run {app}",
            },
            "resources": {
                "exact": "-N{nodes} -n {tasks}",
                "verbatim": "on {nodes} nodes and {tasks} tasks (-N{nodes} -n {tasks})",
                "descriptive": "execute {app} across {nodes} nodes with {tasks} ranks",
                "discovery": "using all available nodes and cores",
            },
            "modifiers": {
                "affinity": {
                    # Tell the generator this goes with 'flux run'
                    "type": "manager",
                    "flag": "-o cpu-affinity=per-task",
                    "variants": {
                        "exact": "flux option -o cpu-affinity=per-task",
                        "verbatim": "setting the flux option -o cpu-affinity=per-task",
                        "descriptive": "ensuring each task is pinned for performance",
                    },
                },
            },
            "syntax": {"run_cmd": "flux submit", "resource_flags": "-N{nodes} -n {tasks}"},
        }

    @property
    def metadata(self) -> Dict[str, Any]:
        """
        High-level capacity and versioning for the Hub.

        Returns:
            Dict: Static manifest including total core and node counts.
        """
        if not self.available or not self.handle:
            return {"installed": False}

        import flux.resource

        try:
            listing = flux.resource.list.resource_list(self.handle).get()
            return {
                "system_type": "flux",
                "total_cores": listing.all.ncores,
                "total_nodes": listing.all.nnodes,
                "status": "online",
            }
        except Exception:
            return {"status": "error", "message": "Failed to query flux resources"}

    # Secretary Tools

    @secretary_tool
    def get_resource_status(self) -> Dict[str, Any]:
        """
        Retrieves detailed real-time availability of cores and nodes.

        Returns:
            Dict: A detailed status including 'free_cores', 'up_nodes', and
                  the 'resource_status' execution list (nodelists).
                  Use this to verify if specific nodes are available for a job.
        """
        import flux.resource

        listing = flux.resource.list.resource_list(self.handle).get()
        resource_status = self.handle.rpc("sched-fluxion-resource.status").get()

        return {
            "free_cores": listing.free.ncores,
            "up_nodes": listing.up.nnodes,
            "resource_status": resource_status,
        }

    @secretary_tool
    def get_queue_stats(self) -> Dict[str, Any]:
        """
        Retrieves statistics from the Fluxion queue manager.

        Returns:
            Dict: Detailed queue depth, job counts (pending, running), and
                  policy-specific timing information. Use this to estimate
                  current cluster pressure and potential wait times.
        """
        # queue depth is returning a value I do not understand.
        response = self.handle.rpc("sched-fluxion-qmanager.stats-get").get()
        results = {}
        for name, queue in response.items():
            if "queue_depth" in queue:
                del queue["queue_depth"]
            results[name] = queue
        return results

    @secretary_tool
    def get_scheduler_params(self) -> Dict[str, Any]:
        """
        Retrieves the active configuration parameters for the Fluxion scheduler.

        Returns:
            Dict: Includes the 'match-format', 'traverser' type, and 'policy'
                  settings. Use this to determine if the scheduler logic
                  aligns with specific user-requested job shapes.
        """
        return self.handle.rpc("sched-fluxion-resource.params").get()

    @secretary_tool
    def get_resource_utilization_stats(self) -> Dict[str, Any]:
        """
        Retrieves low-level graph and matching statistics for the resources.

        Returns:
            Dict: Includes 'match' success/fail rates and 'graph-uptime'.
                  Use this to diagnose if the scheduler is failing to place
                  jobs due to high fragmentation or resource errors.
        """
        return self.handle.rpc("sched-fluxion-resource.stats-get").get()
