from typing import Any, Dict

from ...provider import secretary_tool
from ..base import MockBaseProvider


class MockMPICHProvider(MockBaseProvider):
    """
    Mock: MPICH.
    """

    def __init__(self, config):
        super().__init__(config)
        self.version = "unknown"
        self._device = "ch4:ofi"

    @property
    def name(self) -> str:
        return "mpich"

    def probe(self) -> bool:
        rng = self.config.get_rng("mpich")
        self.version = rng.choice(["3.4.3", "4.0.2", "4.1.1"])
        # Scale/Archetype determines the underlying device
        self._device = "ch4:ofi" if self.config.archetype.name == "hpc" else "ch3:nemesis"
        self.available = True
        return True

    @secretary_tool
    def get_build_info(self) -> str:
        """
        Mock mpichversion: Returns detailed build and device information.
        """
        return (
            f"MPICH Version:    {self.version}\n"
            f"MPICH Release date: Mon Apr 10 10:42:15 CDT 2023\n"
            f"MPICH Device:      {self._device}\n"
            f"Configure options: --with-device={self._device} --enable-fortran"
        )

    def export_truth(self) -> Dict[str, Any]:
        return {"version": self.version, "device": self._device}
