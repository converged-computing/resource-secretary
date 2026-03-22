import os
import time
from typing import Any, Dict, List, Optional

from ..provider import BaseProvider, secretary_tool


class FluxProvider(BaseProvider):
    """
    The Flux provider interacts with the Flux Framework using native Python bindings.
    It provides modular tools for deep investigation of scheduler state,
    resource utilization, and queue parameters.
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
        return self.handle.rpc("sched-fluxion-qmanager.stats-get").get()

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
