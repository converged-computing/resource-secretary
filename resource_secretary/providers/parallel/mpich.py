import shutil
import subprocess
from typing import Any, Dict

from ..provider import BaseProvider, secretary_tool


class MPICHProvider(BaseProvider):
    """
    Specialized provider for MPICH implementations.
    """

    def __init__(self):
        super().__init__()
        self.available = False

    @property
    def name(self) -> str:
        return "mpich"

    def probe(self) -> bool:
        """
        Checks for the presence of mpichversion.
        """
        self.available = shutil.which("mpichversion") is not None
        return self.available

    @property
    def metadata(self) -> Dict[str, Any]:
        """
        Returns MPICH version and configuration details.
        """
        version_out = "unknown"
        if self.available:
            try:
                version_out = subprocess.check_output(["mpichversion"], text=True).splitlines()[0]
            except:
                pass
        return {"version": version_out, "launcher": shutil.which("mpiexec")}

    @secretary_tool
    def get_mpich_info(self) -> str:
        """
        Retrieves full configuration and device information for MPICH.

        Returns:
            str: Detailed output from mpichversion.
        """
        try:
            return subprocess.check_output(["mpichversion"], text=True).strip()
        except Exception as e:
            return str(e)
