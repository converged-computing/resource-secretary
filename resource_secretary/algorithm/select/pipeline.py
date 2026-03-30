from typing import Any, Dict, List

from .base import BaseSelector, SelectionResult, SelectionStatus


class SelectorPipeline(BaseSelector):
    """
    The standard runner for selection. It executes a sequence of
    selectors until one returns SELECTED or the list is exhausted.
    """

    metadata = {
        "name": "select_pipeline",
        "description": "Sequential selection: Attempts multiple selection strategies in order until one succeeds.",
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "proposals": {"type": "object"},
                "strategies": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of strategy names to try in order",
                },
            },
            "required": ["prompt", "proposals", "strategies"],
        },
    }

    def __init__(self, selectors: List[BaseSelector], **kwargs):
        super().__init__(**kwargs)
        self.selectors = selectors

    async def select(self, prompt: str, proposals: Dict[str, Any]) -> SelectionResult:
        failures = []

        for selector in self.selectors:
            name = selector.__class__.__name__
            result = await selector.select(prompt, proposals)

            if result.status == SelectionStatus.SELECTED:
                # Track which algorithm made the final call
                result.metadata["algorithm"] = name
                return result

            failures.append(f"{name}: {result.reasoning}")

        return SelectionResult(
            status=SelectionStatus.REJECTED,
            reasoning=f"All selection strategies failed. {'; '.join(failures)}",
        )
