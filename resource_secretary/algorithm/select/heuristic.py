import json
import random
from typing import Any, Dict

import resource_secretary.utils as utils

from .base import BaseSelector, SelectionResult, SelectionStatus, WorkerProposal, WorkerVerdict

# These are designed to handle a textual response from an agent (with a code block that has "verdict")
# or a proposal[wid].actual_verdict outside of the response.


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
            verdict = resp.get("actual_verdict")
            try:
                data = json.loads(utils.extract_code_block(raw_text))
                # Preference to actual verdict
                verdict = verdict or data.get("verdict")
                if verdict == WorkerVerdict.READY:
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
            verdict = resp.get("actual_verdict")
            raw_text = resp.get("data", {}).get("proposal", "")
            try:
                data = json.loads(utils.extract_code_block(raw_text))
                # Preference to actual verdict
                verdict = verdict or data.get("verdict")
                if verdict == WorkerVerdict.READY:
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
    Finds the worker with the shortest queue depth. as a proxy for start.
    """

    metadata = {
        "name": "select_soonest",
        "description": "Throughput-optimized selection: Compares cluster depth and picks the worker that will start the job the soonest. Use when the user wants to minimize wait time.",
        "parameters": BaseSelector.metadata["parameters"],
    }

    async def select(self, prompt: str, proposals: Dict[str, Any]) -> SelectionResult:
        best_wid, min_depth = None, float("inf")
        for wid, resp in proposals.items():
            verdict = resp.get("actual_verdict")
            raw_text = resp.get("data", {}).get("proposal", "")
            metrics = resp.get("metrics", {})
            try:
                data = json.loads(utils.extract_code_block(raw_text))
                # Preference to actual verdict
                verdict = verdict or data.get("verdict")
                if verdict in [WorkerVerdict.READY, WorkerVerdict.BUSY]:
                    depth = metrics.get("queue_depth", float("inf"))
                    if depth < min_depth:
                        min_depth, best_wid = depth, wid
            except:
                continue

        if best_wid:
            return SelectionResult(
                worker_id=best_wid,
                status=SelectionStatus.SELECTED,
                reasoning=f"Smallest queue depth: {min_depth} jobs.",
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
            verdict = resp.get("actual_verdict")
            raw_text = resp.get("data", {}).get("proposal", "")
            try:
                data = json.loads(utils.extract_code_block(raw_text))
                verdict = verdict or data.get("verdict")
                if verdict == WorkerVerdict.READY:
                    candidates.append((wid, "READY"))
                elif verdict == WorkerVerdict.BUSY:
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


class DynamicQueueSelector(BaseSelector):
    """
    Load-balancing selection: Picks the worker with the lowest simulated queue depth.
    """

    metadata = {
        "name": "select_dynamic_queue",
        "description": "Load-balancing selection: Compares the current live queue depth across the fleet and picks the worker with the fewest pending jobs. Use for maximizing system throughput. Requires metrics.queue_depth",
        "parameters": BaseSelector.metadata["parameters"],
    }

    async def select(self, prompt: str, proposals: Dict[str, Any]) -> SelectionResult:
        best_wid, min_queue = None, float("inf")

        for status in [WorkerVerdict.READY, WorkerVerdict.BUSY]:
            for wid, resp in proposals.items():
                verdict = resp.get("actual_verdict")
                raw_text = resp.get("data", {}).get("proposal", "")
                try:
                    data = json.loads(utils.extract_code_block(raw_text))
                    verdict = verdict or data.get("verdict")
                    if verdict == status:
                        queue = resp.get("metrics", {}).get("queue_depth", float("inf"))
                        if queue < min_queue:
                            min_queue, best_wid = queue, wid
                except:
                    continue

            if best_wid:
                return SelectionResult(
                    worker_id=best_wid,
                    status=SelectionStatus.SELECTED,
                    reasoning=f"Least busy compatible worker found. Queue Depth: {min_queue} jobs.",
                )
        return SelectionResult(
            status=SelectionStatus.REJECTED,
            reasoning="No READY workers available in the current simulation state.",
        )


class MinCostSelector(BaseSelector):
    """
    Economic selection: Picks the worker with the lowest total cost.
    """

    metadata = {
        "name": "select_min_cost",
        "description": "Economic selection: Compares calculated total cost (node + cpu + gpu) across all compatible workers and picks the cheapest option. Requires metrics.total_cost.",
        "parameters": BaseSelector.metadata["parameters"],
    }

    async def select(self, prompt: str, proposals: Dict[str, Any]) -> SelectionResult:
        best_wid, min_cost = None, float("inf")

        # Try for ready, then busy
        for status in [WorkerVerdict.READY, WorkerVerdict.BUSY]:
            for wid, resp in proposals.items():
                raw_text = resp.get("data", {}).get("proposal", "")
                verdict = resp.get("actual_verdict")

                try:
                    data = json.loads(utils.extract_code_block(raw_text))
                    verdict = verdict or data.get("verdict")
                    if verdict == status:
                        cost = resp.get("metrics", {}).get("total_cost", float("inf"))
                        if not cost:
                            continue
                        if cost < min_cost:
                            min_cost, best_wid = cost, wid
                except:
                    continue

            if best_wid:
                return SelectionResult(
                    worker_id=best_wid,
                    status=SelectionStatus.SELECTED,
                    reasoning=f"Cheapest compatible worker found. Estimated Cost: ${min_cost:.4f}",
                )
        return SelectionResult(
            status=SelectionStatus.REJECTED, reasoning="No READY workers found to calculate cost."
        )
