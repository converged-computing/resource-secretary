from typing import List, Union

from .agentic import AgenticSelector
from .base import BaseSelector, SelectionResult, SelectionStatus, WorkerVerdict  # noqa
from .heuristic import (
    DynamicQueueSelector,
    FirstReadySelector,
    MinCostSelector,
    RandomSelector,
    RunAnytimeSelector,
    SoonestSelector,
)
from .pipeline import SelectorPipeline

STRATEGIES = {
    "first-ready": FirstReadySelector,
    "random": RandomSelector,
    "soonest": SoonestSelector,
    "run-anytime": RunAnytimeSelector,
    "agentic": AgenticSelector,
    "min-cost": MinCostSelector,
    "queue-depth": DynamicQueueSelector,
    # TODO add cost related
}


def get_selector(names: Union[str, List[str]], **kwargs) -> SelectorPipeline:
    """
    Always returns a SelectorPipeline containing the requested strategies.

    Suggestions from v:

    "Be Smart, then Desperate":
    get_selector(["agentic", "run-anytime"], agent=my_agent)

    "Balanced immediate execution":
    get_selector(["soonest", "random"])

    "The Desperation Fallback":
    get_selector(["first-ready", "run-anytime"])

    Someone is rolling in their grave seeing any kind of algorithm I make.
    Roll away, Merrill. Roll away.
    """
    if isinstance(names, str):
        names = [names]

    pipeline_instances = []
    for name in names:
        if name not in STRATEGIES:
            raise ValueError(f"Unknown selection strategy: {name}")
        pipeline_instances.append(STRATEGIES[name](**kwargs))

    return SelectorPipeline(selectors=pipeline_instances)
