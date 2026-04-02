import shutil
import subprocess
from typing import Any, Dict, List, Optional

from ..provider import BaseProvider


class GPUProviderBase(BaseProvider):
    """
    Intermediate logic for GPU hardware discovery.
    """

    is_provider = False

    def __init__(self):
        super().__init__()
        self.bin_path: Optional[str] = None

    def run_smi_cmd(self, args: List[str]) -> str:
        """
        Executes a vendor SMI tool directly.
        """
        if not self.bin_path:
            return "Error: SMI tool not found."
        try:
            result = subprocess.run(
                [self.bin_path] + args, capture_output=True, text=True, timeout=10
            )
            return result.stdout.strip()
        except Exception as e:
            return f"Error executing {self.name} tool: {str(e)}"
