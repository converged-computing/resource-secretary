import shutil
import subprocess
from typing import Any, Dict, List, Optional

from ..provider import BaseProvider, secretary_tool


class OCIProvider(BaseProvider):
    """
    Internal Base: Carries the logic but is NOT a provider.
    is_provider remains False.
    """

    is_provider = False

    def __init__(self):
        super().__init__()
        self.bin_path: Optional[str] = None

    def run_command(self, args: List[str]) -> str:
        if not self.bin_path:
            return "Error: Binary not found."
        try:
            result = subprocess.run(
                [self.bin_path] + args, capture_output=True, text=True, timeout=10
            )
            return result.stdout.strip()
        except Exception as e:
            return f"Error: {str(e)}"

    @secretary_tool
    def list_images(self, filter: str = "") -> str:
        """Lists available images in this specific runtime's storage."""
        args = ["images"]
        if filter:
            args.append(filter)
        return self.run_command(args)


class DockerProvider(OCIProvider):
    """
    Provider for Docker
    """

    is_provider = True

    @property
    def name(self) -> str:
        return "docker"

    def probe(self) -> bool:
        self.bin_path = shutil.which("docker")
        return self.bin_path is not None

    @property
    def metadata(self) -> Dict[str, Any]:
        return {"version": self.run_command(["--version"]), "path": self.bin_path}


class PodmanProvider(OCIProvider):
    """
    Provider for Podman
    """

    is_provider = True

    @property
    def name(self) -> str:
        return "podman"

    def probe(self) -> bool:
        self.bin_path = shutil.which("podman")
        return self.bin_path is not None

    @property
    def metadata(self) -> Dict[str, Any]:
        return {"version": self.run_command(["--version"]), "path": self.bin_path}
