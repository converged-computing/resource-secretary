from typing import Any, Dict

from ...provider import secretary_tool
from ..base import MockBaseProvider


class MockContainerProvider(MockBaseProvider):
    def __init__(self, config, runtime, rootless=False):
        super().__init__(config)
        self.runtime = runtime
        self.rootless = rootless

    @property
    def name(self) -> str:
        return self.runtime

    def probe(self) -> bool:
        self.available = True
        return True

    @secretary_tool
    def get_container_info(self) -> Dict[str, Any]:
        return {"runtime": self.runtime, "rootless": self.rootless, "version": "1.0.0"}

    def export_truth(self):
        return {"runtime": self.runtime, "rootless": self.rootless}


class MockDockerProvider(MockContainerProvider):
    def __init__(self, config):
        super().__init__(config, "docker", rootless=False)


class MockPodmanProvider(MockContainerProvider):
    def __init__(self, config):
        super().__init__(config, "podman", rootless=True)


class MockSingularityProvider(MockBaseProvider):
    def __init__(self, config):
        super().__init__(config)

    @property
    def name(self) -> str:
        return "singularity"

    def probe(self) -> bool:
        return True

    @secretary_tool
    def check_singularity(self) -> str:
        return "singularity version 3.8.0-flow"

    def export_truth(self):
        return {"runtime": "singularity", "rootless": True}
