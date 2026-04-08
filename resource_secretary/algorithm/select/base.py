from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class WorkerVerdict(str, Enum):
    READY = "READY"
    BUSY = "BUSY"
    # These require reasons
    RESTRICTED = "RESTRICTED"
    INCOMPATIBLE = "INCOMPATIBLE"


class SelectionStatus(str, Enum):
    SELECTED = "SELECTED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


class WorkerProposal(BaseModel):
    """
    The structured part of the worker's response.
    """

    verdict: WorkerVerdict
    reasoning: str
    metrics: Dict[str, int] = {"queue_depth": 0, "ets_seconds": 0}
    constraints: List[str] = []


class SelectionResult(BaseModel):
    """
    The final decision of the selection algorithm.
    """

    worker_id: Optional[str] = None
    status: SelectionStatus
    reasoning: str
    metadata: Dict[str, Any] = {}


class BaseSelector:
    """
    Base class for all selection algorithms with Tool Metadata.

    I am adding the tool metadata with the idea that the agent can eventually choose
    the selector to use based on the user query.
    """

    # Metadata to be overwritten by subclasses
    metadata = {
        "name": "base_selector",
        "description": "Base selector interface.",
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "The original job request"},
                "proposals": {
                    "type": "object",
                    "description": "The dictionary of worker proposals",
                },
            },
            "required": ["prompt", "proposals"],
        },
    }

    def __init__(self, **kwargs):
        self.options = kwargs

    async def select(self, prompt: str, proposals: Dict[str, Any]) -> SelectionResult:
        raise NotImplementedError("Subclasses must implement select()")
