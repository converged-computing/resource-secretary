import os
import shutil
from typing import Any, Dict

from ..provider import secretary_tool
from .workload import WorkloadProviderBase


class OARProvider(WorkloadProviderBase):
    """
    Handles discovery for the OAR resource manager.
    """

    is_provider = True

    @property
    def name(self) -> str:
        return "oar"

    def probe(self) -> bool:
        """
        Checks for oarsub binary.
        """
        self.bin_path = shutil.which("oarsub")
        return self.bin_path is not None

    @property
    def metadata(self) -> Dict[str, Any]:
        """
        Returns OAR version.
        """
        return {"version": self.run_workload_cmd(["oarnodes", "--version"])}

    @secretary_tool
    def get_resources(self) -> str:
        """
        Retrieves the list of resources and their current state in OAR.

        Returns:
            str: Output of 'oarnodes'.
        """
        return self.run_workload_cmd(["oarnodes"])
