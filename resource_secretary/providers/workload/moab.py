import shutil
from typing import Any, Dict

from ..provider import secretary_tool
from .workload import WorkloadProviderBase


class MoabProvider(WorkloadProviderBase):
    """
    Handles discovery for the Moab cluster scheduler.
    """

    is_provider = True

    @property
    def name(self) -> str:
        return "moab"

    def probe(self) -> bool:
        """
        Checks for msub binary.
        """
        self.bin_path = shutil.which("msub")
        return self.bin_path is not None

    @property
    def metadata(self) -> Dict[str, Any]:
        """
        Returns Moab version.
        """
        return {"version": self.run_workload_cmd(["msub", "--version"])}

    @secretary_tool
    def get_showq(self) -> str:
        """
        Retrieves the summarized queue status from Moab.

        Returns:
            str: Output of 'showq'. Use this to see current job backlog.
        """
        tool = shutil.which("showq")
        return self.run_workload_cmd([tool]) if tool else "showq not found"
