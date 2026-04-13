import json
import operator
import sys
from typing import Any, Dict, List

from rich import print

import resource_secretary.utils as utils


class SimulationAuditor:
    """
    The 'Omniscient Scorer'. Programmatically determines if a mock worker
    satisfies a requirement logic without using an LLM.
    """

    def __init__(self):
        self.ops = {">=": operator.ge, "<=": operator.le, "==": operator.eq}

    def evaluate(
        self, worker_truth: dict, requirement: dict, agent_resp: dict, tool_registry: dict
    ) -> dict:
        """
        Audit an agent interaction

        1. Checks for the accuracy of the response.
        2. Checks tool calls - if the agent inspected as we'd expect.
        """
        # real ground truth verdict
        # for this, we assume if the user says NOW that is a requirement
        missing_requirements = self.check_satisfaction(worker_truth, requirement)
        is_satisfied = not missing_requirements
        for missing in missing_requirements:
            print(missing)

        # Compare with agent's reported Verdict
        agent_data = agent_resp.get("data", {}).get("proposal")
        if not agent_data:
            print(f"Missing agent data response: {agent_resp}")
            return {}

        # Store initial (full response) to keep/
        # The agent makes a lot of deliberation, but this is what matters.
        agent_response = agent_data

        # Audit the tool calls (Did the agent just get lucky?)
        calls = []
        if "CALLS" in agent_data:
            try:
                agent_data, calls_block = agent_data.split("CALLS")
                calls = utils.format_calls(calls_block)
            except:
                print(f"Issue parsing calls, agent had malformed response: {agent_data}")
                pass

        # Unknown (timeout) vs. Malformed response (very rare, but in a few hundred I saw one)
        try:
            if "UNKNOWN" in agent_data:
                agent_data = {"verdict": "UNKNOWN", "reason": "Deliberation timed out."}
            else:
                agent_data = json.loads(utils.extract_code_block(agent_data))
        except:
            agent_data = {"verdict": "UNKNOWN", "reason": "Malformed response"}

        # Always get the verdict from the data.
        agent_verdict = agent_data.get("verdict", "UNKNOWN").upper()

        # if actually INCOMPATIBLE need to parse just MISSING and only
        # require tool calls for that. We would not need to keep searching
        categories = None
        if not is_satisfied:
            categories = set([x.split(":", 1)[0] for x in missing_requirements])
            print(
                f"Work is not possible, only requiring calls that would determine something missing: {categories}"
            )

        # once we determined not compatible.
        trace_audit = self.audit_trace(requirement, calls, tool_registry, categories)
        actual_verdict = "COMPATIBLE" if is_satisfied else "INCOMPATIBLE"

        # If the agent says busy and we can satisfy the work, this is a valid response
        # This returns a missing statement if we ARE busy
        is_busy = len(self.verify_temporal(worker_truth, requirement.get("logic", {}))) > 0

        # The cluster is actually busy
        if is_busy and actual_verdict == "COMPATIBLE":
            actual_verdict = "BUSY"

        # If we can satisfy and are busy, the final actual verdict is BUSY
        justification = self.get_justification(
            agent_verdict, is_satisfied, worker_truth, requirement
        )

        # The agent is correct if said can be READY/BUSY/RESTRICTED and the cluster can satisfy
        is_correct = justification["is_valid"]
        actual_verdict = justification["actual_state"]
        print(f"Agent verdict: '{agent_verdict}'")
        print(f"Actual verdict: '{actual_verdict}'")
        print(f"Was the agent correct? {is_correct}")

        # A rigorous response is one where the verdict is correct
        # AND the agent called all necessary tools.
        is_rigorous = is_correct and (trace_audit["score"] == 1.0)

        return {
            # These first two are essentially the same.
            "verdict": {
                "actual_verdict": actual_verdict,
                "agent_verdict": agent_verdict,
                # Can the cluster actually handle the work
                # not accounting for time
                "is_satisfied": is_satisfied,
                # Was the agent response correct
                "is_correct": is_correct,
                # Was the agent response justified
                "is_justified": justification["is_valid"],
                "is_justified_reason": justification["reason"],
                # the verfict is correct and the agent called all necessary tools
                "is_rigorous": is_rigorous,
            },
            "report": {
                "trace": trace_audit,
                "reasoning": agent_data,
                "calls": calls,
                "missing_requirements": missing_requirements,
                "response": agent_response,
            },
        }

    def determine_manager(self, truth):
        """
        Extracts idle nodes from Slurm or Flux truth.
        """
        for manager in ["slurm", "flux", "kubernetes", "machine"]:
            if manager in truth["workload"]:
                return manager
        raise ValueError(f"manager {manager} not accounted for.")

    def get_idle_count(self, truth):
        """
        Extracts idle nodes from Slurm or Flux truth.
        """
        manager = self.determine_manager(truth)
        return truth["workload"][manager]["idle_nodes"]

    def get_total_nodes(self, truth):
        """
        Extracts cores per node
        """
        manager = self.determine_manager(truth)
        return truth["workload"][manager]["total_nodes"]

    def get_cores_per_node(self, truth):
        """
        Extracts cores per node for a non-standalone
        """
        manager = self.determine_manager(truth)
        return truth["workload"][manager]["cores_per_node"]

    def get_idle_count(self, truth):
        """
        Extracts idle nodes from Slurm or Flux truth.
        """
        manager = self.determine_manager(truth)
        return truth["workload"][manager]["idle_nodes"]

    def get_justification(self, agent_verdict, is_compatible, worker_truth, requirement):
        """
        Based on an agent response, compare against truth to determine if valid.
        E.g., if the agent says BUSY, make sure the cluster is busy.
        """
        justification = {"is_valid": False, "reason": ""}
        logic = requirement["logic"]

        # Justified if compatible but no idle resources
        idle = self.get_idle_count(worker_truth)

        # Can we determine busy? We always can for the cluster, but if we do not
        # generate a prompt that considers a state of busy-ness (job size)
        # we just are looking for compatible / not. So busy is a subset of
        # compatible
        busy = "unknown"
        compatible_status = "COMPATIBLE"

        if "compute" in logic:
            if logic["compute"]["unit"] == "cores":
                cores_needed = logic["compute"]["count"]
                nodes_needed = int(cores_needed / self.get_cores_per_node(worker_truth))
            else:
                nodes_needed = logic["compute"]["count"]

            # If we have enough nodes for the work?
            busy = "no" if idle >= nodes_needed else "yes"

            # If we get a compatible, we can also determine busy
            if busy == "yes":
                compatible_status = "BUSY"

        if agent_verdict == "UNKNOWN":
            justification = {
                "is_valid": False,
                "reason": "The agent was unable to complete the task, likely max attempts.",
                "actual_state": compatible_status if is_compatible else "INCOMPATIBLE",
            }

        elif agent_verdict == "INCOMPATIBLE":
            # Agent said not compatible, and it isn't.
            if not is_compatible:
                justification = {
                    "is_valid": True,
                    "reason": "System fundamentally lacks resource.",
                    "actual_state": "INCOMPATIBLE",
                }

            # Agent said not compatible, but it is.
            else:
                justification = {
                    "is_valid": False,
                    "reason": "Agent claimed incompatible, but system has capability",
                    "actual_state": compatible_status,
                }

        elif agent_verdict == "READY":
            # Agent said ready and we are compatible
            if is_compatible:
                justification = {
                    "is_valid": True,
                    "reason": "System meets all constraints and is READY",
                    "actual_state": "READY",
                }
            # Agent said ready but we aren't compatible, won't work.
            else:
                justification = {
                    "is_valid": False,
                    "reason": "Agent said READY but constraints failed",
                    "actual_state": "INCOMPATIBLE",
                }

        # We assume busy means it cannot be received now
        elif agent_verdict == "BUSY":

            # If we have enough nodes for the work?
            if is_compatible and busy == "yes":
                justification = {
                    "is_valid": True,
                    "reason": "System compatible but currently fully allocated",
                    "actual_state": "BUSY",
                }
            elif is_compatible:
                justification = {
                    "is_valid": True,
                    "reason": "System compatible, agent determined busy but state is unknown.",
                    "actual_state": compatible_status,
                }
            # busy no
            else:
                justification = {
                    "is_valid": False,
                    "reason": "Agent said BUSY but system has idle capacity",
                    "actual_state": "READY",
                }

        elif agent_verdict == "RESTRICTED":
            if is_compatible:
                justification = {
                    "is_valid": True,
                    "reason": "Agent found restricted, but compatible. Needs human verification",
                    "actual_state": "COMPATIBLE" if busy in ["no", "unknown"] else "BUSY",
                }
            else:
                justification = {
                    "is_valid": False,
                    "reason": "Agent found restricted, but not compatible. Incorrect response.",
                    "actual_state": "INCOMPATIBLE",
                }
        return justification

    def audit_trace(
        self, requirement: dict, calls: list, tool_registry: dict, required_categories=None
    ) -> dict:
        """
        Grades the agent's procedure by matching actual calls against
        the provider categories. This is not a validation of whether the agent
        can satisfy the request actually or not, but whether it requested the right
        tools to determine if it can/cannot.

        tool_registry: { 'software': ['spack.find_package', ...], 'hardware': [...] }
        actual_calls:  [ {'provider': 'spack', 'function': 'find_package'}, ... ]
        """
        logic = requirement["logic"]
        required_categories = required_categories or set(logic.keys())

        # If we ask for a container technology we do not require software calls
        if "container" in logic and "software" in logic and "software" in required_categories:
            required_categories.remove("software")

        # Compute hardware is either cpu/gpu
        if "compute" in required_categories:
            required_categories.remove("compute")
            # This could be for gpu or cpu info
            required_categories.add("hardware")

        # Flatten actual calls into "provider.function" strings
        # called tools are ALL called tools that were actually done
        called_tools = {}

        # Keep full names too.
        trace_strings = []
        print("calls")
        print(calls)
        for call in calls:
            # Clean up args if we don't have any, smaller json
            if not call["args"]:
                del call["args"]

            trace_strings.append(f"{call['provider']}.{call['function']}")
            provider = call["provider"]
            if provider not in called_tools:
                called_tools[provider] = set()
            called_tools[provider].add(call["function"])

        results = {"score": 0.0, "categories": {}, "actual_calls": trace_strings}
        satisfied_count = 0

        for cat in required_categories:

            # These are valid tools for the category so we can associate
            # a provider with category. E.g., spack is software
            valid_tools_for_cat = set(tool_registry.get(cat, []))

            # Did the agent call at least one tool from this category?
            actual_called_tools = set()

            # temporal requirements need workload manager calls
            if cat == "temporal":
                valid_tools_for_cat = set(tool_registry.get("workload", []))

            # Get all valid tools registered for this directory category
            # These have the provider extension, so we need to cut.
            potential_tools = set()
            for potential_tool in valid_tools_for_cat:
                provider, call_name = potential_tool.split(".", 1)
                potential_tools.add(call_name)
                # Was it called?
                if potential_tool in trace_strings:
                    actual_called_tools.add(call_name)

            potential_called = len(potential_tools)
            number_called = len(actual_called_tools)
            satisfied = number_called > 0

            # If there aren't valid tools, the agent is always ok - can't make a call
            # We don't count the category
            if not potential_tools:
                continue

            # No division by 0!
            percentage_explored = 0
            if potential_called > 0:
                percentage_explored = number_called / potential_called

            # TODO add check for number out of total (total search done)
            results["categories"][cat] = {
                "satisfied": satisfied,
                "number_called": number_called,
                "actual_tools": actual_called_tools,
                "potential_tools": potential_tools,
                "actual_calls": potential_called,
                "percentage_calls_explored": percentage_explored,
            }
            if satisfied:
                satisfied_count += 1

        if required_categories:
            results["score"] = satisfied_count / len(required_categories)

        return results

    def verify_container(self, truth: dict, req: dict) -> bool:
        """
        Verify a container runtime
        """
        requested_runtime = req["runtime"]
        if "container" not in requested_runtime:
            return []
        if requested_runtime not in truth["container"]:
            # Allow sub for docker/podman - they are "same"
            if requested_runtime == "docker" and "podman" in truth["container"]:
                return []
            if requested_runtime == "podman" and "docker" in truth["container"]:
                return []
            return [f"container: {requested_runtime} is missing."]
        return []

    def check_satisfaction(self, worker_truth: Dict[str, Any], requirement: Dict[str, Any]) -> bool:
        """
        Returns True if the worker_truth satisfies every dimension in the requirement logic.
        """
        logic = requirement.get("logic", {})
        print(logic)
        total_missing = []

        # Special case agent should NOT look for app installed, just container
        if ("software" in logic and "container" in logic) or "container" in logic:
            # If we have container, this is a special case where we don't need to call for software.
            # we do not penalize for it, but we don't penalize for not doing it.
            total_missing += self.verify_container(worker_truth, logic["container"])

        # Software Check (Agnostic across Spack, Conda, Modules)
        # Do an evaluation for everything that is missing.
        elif "software" in logic:
            total_missing += self.verify_software(worker_truth, logic)

        # Compute Scale Check (Cores or Nodes)
        if "compute" in logic:
            total_missing += self.verify_compute(worker_truth, logic["compute"])

        # Environment Check (Fabric and Storage)
        if "network" in logic:
            total_missing += self.verify_network(worker_truth, logic["network"])
        if "storage" in logic:
            total_missing += self.verify_storage(worker_truth, logic["storage"])

        # Temporal Check (Urgency/Busyness)
        if "temporal" in logic:
            total_missing += self.verify_temporal(worker_truth, logic)

        return total_missing

    def verify_software(self, truth: dict, requirement: dict) -> bool:
        """
        Check to see what is missing. Return True/False [missing]
        """
        req = requirement["software"]
        app_name = req["name"].lower()
        target_version = req.get("version")
        package_name = f"{app_name}@{target_version}"
        missing = []

        # Preparing missing messages
        missing_version = f"software: {app_name}@{target_version} is missing"
        missing_mismatch = f"software: {app_name}@{target_version} has another version, but this requirement is not satisfied."

        # if version defined but not op, assume ==
        # if version not provided, assume any
        op_sym = req.get("op")
        if target_version is not None and op_sym is None:
            op_sym = "=="

        elif target_version is None:
            op_sym = None
            missing_version = f"software: {app_name} is missing"

        # This is a case where we might have satisfied asking for different version

        # Aggregate all software found across all provider types
        found_instances = []

        # Check Spack
        if "spack" in truth["software"]:
            pkgs = truth["software"]["spack"]["manifest"]
            spack_installs = parse_version(pkgs, app_name)
            found_instances += spack_installs

            # If we find something, also look at gpu/cuda and mpi support
            # Note that compute won't be present for very simple requests
            if spack_installs and "compute" in requirement:

                # Mostly debugging
                spack_manifest = truth["software"]["spack"]["manifest"]
                if package_name not in spack_manifest:
                    print(f"Missing {package_name} in spack manifest.")
                    print(truth["software"]["spack"]["manifest"])
                else:
                    # Important - if we require gpus, we need spack variant with cuda
                    gpus = requirement["compute"]["gpus"]
                    if gpus > 0 and not spack_manifest[package_name]["variants"]["cuda"]:
                        missing.append(
                            f"software: {package_name} is not configured for required CUDA support."
                        )

                    # If we need MPI, we also need mpi support
                    if "parallel" in requirement and "mpi" in requirement["parallel"]:
                        if not spack_manifest[package_name]["variants"]["mpi"]:
                            missing.append(
                                f"software: {package_name} is not configured for required MPI support."
                            )

        # Check Modules
        if "modules" in truth["software"]:
            # Lookup with module catories as keys (so each value is list)
            for mods in truth["software"]["modules"]["modules"].values():
                found_instances += parse_version(mods, app_name)

        # Check Conda (currently squash across envs)
        if "conda" in truth["software"]:
            for pkgs in truth["software"]["conda"]["installs"].values():
                found_instances += parse_version(pkgs, app_name)

        # and pip
        if "pip" in truth["software"]:
            for pkgs in truth["software"]["pip"]["installs"].values():
                found_instances += parse_version(pkgs, app_name)

        # Did not find anything, and we needed a version
        if not found_instances:
            missing.append(missing_version)
            return missing

        # or found instances but no version specified (we are good)
        if not target_version:
            return []

        # Version Comparison Logic
        for instance in found_instances:
            version = instance[1]

            # We are looking for a version, we don't have one here.
            if not version:
                continue

            try:
                # Basic numeric comparison for year-based/semver mocks
                if self.ops[op_sym](float(version), float(target_version)):
                    return []

            # Fallback to string match if not numeric
            except (ValueError, KeyError):
                if version == target_version:
                    return []

        missing.append(missing_mismatch)
        return missing

    def verify_compute(self, truth: dict, req: dict) -> bool:
        """
        Node and cores count. What about GPU?
        """
        count = req["count"]
        unit = req["unit"]
        gpus = req["gpus"]
        hardware = truth["hardware"]
        cores = hardware["hardware"]["cpu"]["cores"]
        manager = (
            truth["workload"].get("flux")
            or truth["workload"].get("slurm")
            or truth["workload"].get("kubernetes")
            or truth["workload"].get("machine")
        )
        missing = []

        # Check gpus per node - is what we need > what we have?
        found_gpus = hardware["hardware"]["gpu"]["count"]
        if gpus > found_gpus:
            missing.append(f"compute: Not enough GPUs per node. Need {gpus} have {found_gpus}")

        # This assumes people are going to ask for total cores not per node.
        # the per node is what the user is going to tweak.
        if unit == "cores":
            # We don't have enough cores
            if cores < count:
                missing.append(f"compute: not enough cores {cores} < {count}")

        # Check cluster node count from Slurm/Flux/Kubernetes
        elif unit == "nodes":
            cluster_nodes = manager.get("total_nodes", 0)

            # We have enough nodes
            if cluster_nodes >= count:
                return missing
            missing.append(f"compute: not enough nodes {cluster_nodes} < {count}")
        return missing

    def verify_storage(self, truth: dict, storage: str) -> bool:
        """
        Look at storage.
        """
        missing_storage = f"storage: missing requested storage {storage}"
        if storage and storage not in truth["storage"]:
            return [missing_storage]
        return []

    def verify_network(self, truth: dict, fabric: str) -> bool:
        """
        Look at fabric (network)
        """
        missing_network = f"network: missing requested fabric {fabric}"
        if fabric and fabric not in truth["network"]:
            return [missing_network]
        return []

    def get_free_capacity(self, truth: dict) -> dict:
        """
        Aggregates idle nodes and cores across any detected workload manager.
        """
        free = {"nodes": 0, "cores": 0}
        for _, manager_truth in truth["workload"].items():
            free["nodes"] += manager_truth["idle_nodes"]
            free["cores"] += manager_truth["idle_cores"]
        return free

    def verify_temporal(self, truth: dict, req: dict) -> bool:
        """
        Validates if 'Urgent' requests can be satisfied right now.
        """
        # Quick exit if our difficulty is not high enough for temporal.
        if "temporal" not in req:
            return []

        # Not urgent, no problem
        if req["temporal"].get("urgency") != "immediate":
            return []

        free = self.get_free_capacity(truth)
        required_count = req["compute"]["count"]
        unit = req["compute"]["unit"]

        # THE AUDIT: Is there enough physically free right now?
        if unit == "nodes" and free["nodes"] < required_count:
            return [
                f"temporal: Not enough free nodes ({free['nodes']} < {required_count}) for urgent job."
            ]
        if unit == "cores" and free["cores"] < required_count:
            return [
                f"temporal: Not enough free cores ({free['cores']} < {required_count}) for urgent job."
            ]
        return []


def parse_version(packages, app_name):
    """
    Parse a version and package
    """
    found_instances = []

    # modules vs conda/spack/pip
    for pkg in packages:
        sep = "@" if "@" in pkg else "/"
        version = None
        if sep in pkg:
            name, version = pkg.split(sep)

        # We will check versions after
        if name.lower() == app_name:
            found_instances.append((pkg, version))
    return found_instances
