import json
from typing import Any, Dict

import resource_secretary.utils as utils

from .base import BaseSelector, SelectionResult, SelectionStatus, WorkerProposal


class AgenticSelector(BaseSelector):
    """
    Uses a SecretaryAgent to weigh the pros/cons of different proposals.
    """

    metadata = {
        "name": "select_agentic",
        "description": "Reasoning-based selection: Uses a Lead Secretary (LLM) to weigh technical reasoning and fit-scores across proposals. Use for complex jobs with specific hardware/software version requirements.",
        "parameters": BaseSelector.metadata["parameters"],
    }

    async def select(self, prompt: str, proposals: Dict[str, Any]) -> SelectionResult:
        """
        Run selection. We don't need to provide the backend here, the SecretaryAgent init will find it.
        """
        from resource_secretary.agents.secretary import SecretaryAgent

        # Note that we are not discovering providers. We might want to discover some other kind
        # of function (support) eventually for the selection, but generally the selection is not
        # done where query can be done.
        agent = SecretaryAgent()

        # Pre-filter incompatible results to save tokens
        compatibles = {
            wid: resp for wid, resp in proposals.items() if "INCOMPATIBLE" not in str(resp)
        }

        # Select from the compatible proposals
        raw_response = await agent.select(prompt, compatibles)

        # Parse result using existing utils...
        try:
            decision_json = utils.extract_code_block(raw_response)
            data = json.loads(decision_json)
        except:
            data = {"status": "UNKNOWN", "reasoning": "Issue loading agent response."}

        return SelectionResult(
            worker_id=data.get("worker_id"),
            status=SelectionStatus(data.get("status", "REJECTED")),
            reasoning=data.get("reasoning", "No reasoning provided."),
        )
