import json
import random
from typing import Any, Dict

import resource_secretary.utils as utils

from .base import BaseSelector, SelectionResult, SelectionStatus, WorkerProposal, WorkerVerdict


class FirstReadySelector(BaseSelector):
    """
    Greedy. Picks the first worker that reports READY.
    """

    metadata = {
        "name": "select_first_ready",
        "description": "Greedy selection: Picks the very first worker that is READY. Use for high-speed dispatch when any available resource is acceptable.",
        "parameters": BaseSelector.metadata["parameters"],
    }

    async def select(self, prompt: str, proposals: Dict[str, Any]) -> SelectionResult:
        for wid, resp in proposals.items():
            raw_text = resp.get("data", {}).get("proposal", "")
            try:
                data = json.loads(utils.extract_code_block(raw_text))
                if data.get("verdict") == WorkerVerdict.READY:
                    return SelectionResult(
                        worker_id=wid,
                        status=SelectionStatus.SELECTED,
                        reasoning=f"Immediate match on {wid}.",
                    )
            except:
                continue
        return SelectionResult(status=SelectionStatus.REJECTED, reasoning="No workers are READY.")


class RandomSelector(BaseSelector):
    """
    Collects ALL workers that are READY and picks one at random.
    Useful for basic load balancing across identical nodes.
    """

    metadata = {
        "name": "select_random_ready",
        "description": "Load-balanced selection: Randomly picks from all workers that are READY. Use to distribute jobs evenly across identical idle clusters.",
        "parameters": BaseSelector.metadata["parameters"],
    }

    async def select(self, prompt: str, proposals: Dict[str, Any]) -> SelectionResult:
        ready_workers = []
        for wid, resp in proposals.items():
            raw_text = resp.get("data", {}).get("proposal", "")
            try:
                data = json.loads(utils.extract_code_block(raw_text))
                if data.get("verdict") == WorkerVerdict.READY:
                    ready_workers.append(wid)
            except:
                continue

        if ready_workers:
            selected = random.choice(ready_workers)
            return SelectionResult(
                worker_id=selected,
                status=SelectionStatus.SELECTED,
                reasoning=f"Randomly selected from {len(ready_workers)} READY workers.",
            )
        return SelectionResult(
            status=SelectionStatus.REJECTED, reasoning="No READY workers to pick from."
        )


class SoonestSelector(BaseSelector):
    """
    Finds the worker with the lowest ETS (Estimated Time to Start).
    """

    metadata = {
        "name": "select_soonest",
        "description": "Throughput-optimized selection: Compares all wait times (ETS) and picks the worker that will start the job the soonest. Use when the user wants to minimize wait time.",
        "parameters": BaseSelector.metadata["parameters"],
    }

    async def select(self, prompt: str, proposals: Dict[str, Any]) -> SelectionResult:
        best_wid, min_ets = None, float("inf")
        for wid, resp in proposals.items():
            try:
                p = WorkerProposal.parse_raw(
                    utils.extract_code_block(resp.get("data", {}).get("proposal", ""))
                )
                if p.verdict in [WorkerVerdict.READY, WorkerVerdict.BUSY]:
                    ets = p.metrics.get("ets_seconds", 0)
                    if ets < min_ets:
                        min_ets, best_wid = ets, wid
            except:
                continue

        if best_wid:
            return SelectionResult(
                worker_id=best_wid,
                status=SelectionStatus.SELECTED,
                reasoning=f"Lowest ETS: {min_ets}s.",
            )
        return SelectionResult(
            status=SelectionStatus.REJECTED, reasoning="No workers provided valid timing."
        )


class RunAnytimeSelector(BaseSelector):
    """
    Desperation, lol. Picks the first worker that is either READY or BUSY.
    As long as the cluster is compatible and eventually available (ETS >= 0), it selects it.
    """

    metadata = {
        "name": "select_run_anytime",
        "description": "Urgency-based random selection: Collects ALL workers that are either READY or BUSY and picks one at random. Use when execution is mandatory, the user doesn't care about queue length, and you want to avoid worker bias.",
        "parameters": BaseSelector.metadata["parameters"],
    }

    async def select(self, prompt: str, proposals: Dict[str, Any]) -> SelectionResult:
        candidates = []
        for wid, resp in proposals.items():
            try:
                p = WorkerProposal.parse_raw(
                    utils.extract_code_block(resp.get("data", {}).get("proposal", ""))
                )
                if p.verdict == WorkerVerdict.READY:
                    candidates.append((wid, "READY"))
                elif p.verdict == WorkerVerdict.BUSY and p.metrics.get("ets_seconds", -1) >= 0:
                    candidates.append((wid, "BUSY"))
            except:
                continue

        if candidates:
            selected_wid, status = random.choice(candidates)
            return SelectionResult(
                worker_id=selected_wid,
                status=SelectionStatus.SELECTED,
                reasoning=f"Randomly selected from {len(candidates)} compatible candidates (Winner was {status}).",
            )

        return SelectionResult(
            status=SelectionStatus.REJECTED, reasoning="No compatible READY or BUSY workers found."
        )
