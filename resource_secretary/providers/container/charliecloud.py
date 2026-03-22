from typing import Any, Dict

from ..provider import secretary_tool
from .base import ContainerProvider


class CharliecloudProvider(ContainerProvider):
    is_provider = True

    @property
    def name(self) -> str:
        return "charliecloud"

    def probe(self) -> bool:
        return self.probe_runtime("ch-run")

    @property
    def metadata(self) -> Dict[str, Any]:
        return {"version": self.run_container_cmd(["--version"])}

    @secretary_tool
    def list_images(self) -> str:
        """
        Lists images available in the Charliecloud storage directory.
        Returns: str: List of image names.
        """
        return self.run_container_cmd(["ch-image", "list"])
