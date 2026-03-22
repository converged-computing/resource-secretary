from typing import Any, Dict

from ..provider import secretary_tool
from .base import ContainerProvider


class ShifterProvider(ContainerProvider):
    is_provider = True

    @property
    def name(self) -> str:
        return "shifter"

    def probe(self) -> bool:
        return self.probe_runtime("shifter")

    @property
    def metadata(self) -> Dict[str, Any]:
        return {"status": "active" if self.available else "not_found"}

    @secretary_tool
    def lookup_image(self, image_name: str) -> str:
        """
        Checks if a specific image is available in the Shifter image manager.
        Inputs: image_name (str): Name/tag of the image (e.g., 'ubuntu:latest').
        Returns: str: Image details or lookup status.
        """
        return self.run_container_cmd(["shifterimg", "lookup", image_name])
