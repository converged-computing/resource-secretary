from typing import Any, Dict

import psutil

from ..provider import BaseProvider, secretary_tool


class MemoryProvider(BaseProvider):
    """
    Handles discovery of system memory (RAM).

    TODO: vsoch: a subset of metadata should be cached (and retrieved). We also need
    to remember this will potentially reflect a login node.
    """

    is_provider = True

    @property
    def name(self) -> str:
        return "memory"

    def probe(self) -> bool:
        """
        Always active to report on memory availability.
        """
        return True

    @property
    def metadata(self) -> Dict[str, Any]:
        """
        Returns total system memory in GB.
        """
        return {"total_gb": round(psutil.virtual_memory().total / (1024**3), 2)}

    @secretary_tool
    def get_available_memory(self) -> Dict[str, Any]:
        """
        Retrieves real-time memory availability.

        Returns:
            Dict: Total, available, and used memory in GB. Use this to
                  verify if a job's memory footprint is supported.
        """
        mem = psutil.virtual_memory()
        return {
            "total_gb": round(mem.total / (1024**3), 2),
            "available_gb": round(mem.available / (1024**3), 2),
            "used_gb": round(mem.used / (1024**3), 2),
            "percent": mem.percent,
        }
