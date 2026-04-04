from typing import Any, Dict

from ...provider import secretary_tool
from ..base import MockBaseProvider


class MockOmniPathProvider(MockBaseProvider):
    """
    Intel Omni-Path Fabric.
    """

    def __init__(self, config):
        super().__init__(config)
        self.available = False
        self.capability_tools = {"network": ["get_opa_details"]}

    def probe(self) -> bool:
        self.hfi_count = 1 if self.config.archetype.name == "hpc" else 0
        self.available = self.hfi_count > 0
        return self.available

    @property
    def metadata(self) -> Dict[str, Any]:
        return {
            "hfi_count": self.hfi_count,
            "devices": ["hfi1_0"] if self.hfi_count > 0 else [],
            "has_opainfo": True,
        }

    @property
    def name(self) -> str:
        return "omnipath"

    @secretary_tool
    def get_opa_details(self) -> str:
        """
        opainfo: Retrieves detailed OPA fabric statistics.
        """
        return (
            "hfi1_0:1 \n"
            "  PortGUID:0x00117501017a58b0\n"
            "  LID:0x0001 LMC:0\n"
            "  LinkState:Active\n"
            "  PhysState:LinkUp\n"
            "  Speed:100Gbps"
        )

    def export_truth(self) -> Dict[str, Any]:
        return {"hfi_count": self.hfi_count}
