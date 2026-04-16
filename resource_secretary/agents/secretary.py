import json
import os
import re
from typing import Any, Dict, List

from rich import print
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

import resource_secretary.utils as utils
from resource_secretary.agents.backends import get_backend

console = Console()


class SecretaryAgent:
    """
    The SecretaryAgent is the secretary for a cluster! It will discover resource providers,
    and then receive a job work request and ask the providers (functions calls) for more information.
    It will return (we hope) an honest response about the cluster ability to receive the job based
    on the user criteria.

    When started in verbose, this will record (save) all interactions, and return to the server hub.
    This is intended for experimental mode or when you want to better understand interactions.
    """

    def __init__(self, providers: List[Any] = None, verbose=False):
        self.providers = providers or []
        self.backend = get_backend()
        self.calls = []
        self.provider_map = {p.name: p for p in self.providers}
        self.verbose = verbose
        self.settings_from_environment()

    def settings_from_environment(self):
        """
        Get max attempts from environment
        """
        self.select_max_attempts = int(os.environ.get("MCP_SERVER_SELECT_MAX_ATTEMPTS") or 10)
        self.negotiate_max_attempts = int(os.environ.get("MCP_SERVER_NEGOTIATE_MAX_ATTEMPTS") or 10)
        self.submit_max_attempts = int(os.environ.get("MCP_SERVER_SUBMIT_MAX_ATTEMPTS") or 10)

    def build_system_context(self, tool_types) -> str:
        """
        Builds the manual and prints the tool table for transparency.
        """
        context = "### CLUSTER SERVICE MANUAL\n"

        table = Table(
            title="Secretary: Available Discovery Tools",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Provider", style="cyan")
        table.add_column("Call Syntax", style="green")

        for provider in self.providers:
            # Important: only for the secretary, not dispatch (control)
            tools = provider.discover_tools(tool_types)

            context += f"\nPROVIDER: {provider.name}\n"
            context += f"L1 Metadata: {json.dumps(provider.metadata)}\n"

            if tools:
                for func_name, info in tools.items():
                    params_dict = info.get("parameters", {})
                    if not isinstance(params_dict, dict):
                        params_dict = {}

                    params_str = ", ".join([f"{k}=val" for k in params_dict.keys()])
                    call_syntax = f"{provider.name}.{func_name}({params_str})"

                    context += f"  - CALL: {call_syntax}\n"

                    # In practice, any calls to spack are ginormous monsters
                    # that need to be controlled otherwise I lose my entire terminal
                    if len(call_syntax) > 1000:
                        call_syntax = call_syntax[:1000]
                    table.add_row(provider.name, call_syntax)

        console.print(table)
        return context

    def execute_call(self, provider_name: str, func_name: str, args: Dict[str, Any]) -> str:
        """
        Executes the function and logs results to the worker console.
        """
        provider = self.provider_map.get(provider_name)
        if not provider:
            print(f"Provider {provider_name} was not found")
            return f"Error: Provider '{provider_name}' not found."

        handler = provider.tools.get(func_name)
        if not handler:
            print(f"Provider {provider_name} is missing function {func_name}")
            return f"Error: Function '{func_name}' not found."

        console.print(
            f"  [bold yellow]↳ DISPATCHING:[/bold yellow] {provider_name}.{func_name}({args})"
        )

        try:
            result = handler(**args)
            res_str = (
                json.dumps(result, indent=2) if isinstance(result, (dict, list)) else str(result)
            )
            console.print(Panel(res_str, title=f"Output: {func_name}", border_style="dim"))
            return res_str
        except Exception as e:
            console.print(f"  [bold red]❌ Error:[/bold red] {str(e)}")
            return f"Error: {str(e)}"

    async def deliberate(
        self, request: str, instructions: str, required_obs=0, max_attempts=10
    ) -> str:
        """
        Deliberate can be a negotiation or a selection (prompt is an argument)
        """
        history = [
            {"role": "system", "content": instructions},
            {"role": "user", "content": f"Request: {request}"},
        ]
        self.calls = []

        # Return if agent attempted to return without observing the system
        no_observation = False

        # Require the agent to make observations (calls)
        print(f"Observations required: {required_obs}")
        print(f"          Max attempts: {max_attempts}")
        print(type(max_attempts))

        for i in range(max_attempts):
            console.print(f"\n[bold magenta]Iteration {i}:[/bold magenta] Asking LLM...")

            # Since "tool calls" are local functions, they are in the text response
            raw_response = self.backend.generate_response(history)
            content, _ = self.backend.extract_content_and_calls(raw_response)

            console.print(Panel(content, title="🧠 LLM Thought/Action", border_style="green"))
            history.append(self.backend.format_assistant_message(raw_response))

            # Look for CALL: provider.function(args)
            calls = re.findall(r"CALL:\s*([\w\-]+)\.([\w\-]+)\((.*)\)", content)
            if not calls:
                if "FINAL PROPOSAL" in content or "FINAL RESULT" in content:

                    # In practice, zero calls often doesn't make sense, but depends on function.
                    if len(self.calls) < required_obs:
                        no_observation = True
                        print(
                            f"Calls done {len(self.calls)} but {required_obs} required, requesting more."
                        )
                        history.append(
                            {
                                "role": "user",
                                "content": f"You are required to make at least {required_obs} calls in the format CALL: provider.function(arg=val).",
                            }
                        )
                        continue

                    console.print("[bold green]✅ Proposal Received.[/bold green]")
                    content = f"EARLY RETURN: {no_observation}\n{content}"
                    if self.verbose:
                        content += f"\nCALLS\n```json\n{json.dumps(self.calls)}\n```"
                    print(content)
                    return content

                history.append(
                    {
                        "role": "user",
                        "content": "Please provide a FINAL PROPOSAL or a Format: CALL: provider.function(arg=val).",
                    }
                )
                continue

            # These are function calls on the classes
            print(f"  Requested calls: {calls}")
            obs = "OBSERVATIONS:\n"
            for call in calls:
                p_name, f_name, args_str = call
                args = utils.parse_args(args_str)
                result = self.execute_call(p_name, f_name, args)

                # Results are usually json, but not always
                self.calls.append({"provider": p_name, "function": f_name, "args": args})
                obs += f"- {p_name}.{f_name}: {result}\n"

            history.append({"role": "user", "content": obs})

        return "TIMEOUT"

    async def submit(self, request: str) -> str:
        """
        Execution. Transforms a request into a concrete job,
        submits it, and verifies success.
        """
        system_context = self.build_system_context(["secretary", "dispatch"])
        instructions = (
            f"{system_context}\n"
            "### EXECUTION PROTOCOL ###\n"
            "1. TRANSLATE: Convert the user's textual request into a submission call.\n"
            "2. You MUST use tool calls to submit, get info, etc..\n"
            "       Format: CALL: provider.function(arg=val)\n"
            "3. NO GENERIC/INTERACTIVE CHAT: Do not explain HOW to use software. You CANNOT ask questions.\n"
            "4. BE HONEST: No faking submit or check. You MUST use CALL to submit, verify, and get info.\n"
            "5. FORBIDDEN: Under no conditions should you touch jobs not related to this task.\n"
            "6. VERIFY: After submission, YOU MUST verify the job is running at least 10 seconds AND has not errored.\n"
            "    You MUST look at the log and then status to verify no error has occurred.\n"
            "    If the user provides an expectation, you MUST check for the condition and retry if it is not met.\n"
            "7. You MUST verify a REAL job ID.\n"
            "8. You MUST make an effort to RETRY if there is error due to the submit command or flags.\n"
            "9. FINAL RESULT: You MUST start with 'FINAL RESULT:'. Detail what was done.\n"
            "10. RECEIPT: Include a JSON block at the end with:\n"
            "   - 'status': (SUCCESS or FAILED)\n"
            "   - 'job_id': The cluster-specific job identifier returned by a tool CALL.\n"
            "   - 'spec': The final command or script used for submission.\n"
            "   - 'reasoning': A summary of the execution steps.\n"
            "\n"
            "Example format:\n"
            "FINAL RESULT: Successfully submitted to the queue.\n"
            "```json\n"
            "{\n"
            '  "status": "SUCCESS",\n'
            '  "job_id": "flux-1234",\n'
            '  "spec": "flux submit -n 4 lammps -i input.in",\n'
            '  "reasoning": "Verified job state in queue via flux jobs."\n'
            "}\n"
            "```"
        )
        # Require at least 2 calls - submit and info
        return await self.deliberate(
            f"EXECUTE REQUEST: {request}", instructions, 2, max_attempts=self.submit_max_attempts
        )

    async def select(self, request: str, proposals: Dict[str, Any], metadata: str = None) -> str:
        """
        Select a job given a set of contender clusters. This is typically run after negotiate,
        and not on a single node, but by the calling client that received proposals back from the hub.
        """
        instructions = (
            "### HUB SELECTION PROTOCOL ###\n"
            "You are the Lead Secretary. You have received proposals from multiple clusters.\n"
            "Your job is to act as the final judge and select the best candidate cluster.\n\n"
            "### MANDATORY PROTOCOL ###\n"
            "1. COMPARE: Evaluate which cluster best matches the hardware, software, and timing requirements.\n"
            "2. PRIORITIZE: READY clusters always beat BUSY clusters unless a BUSY cluster has a significantly "
            "better hardware match (e.g., exact software version vs. a compatible one).\n"
            "3. RANK: If multiple clusters are BUSY, choose the best one, and tell why.\n"
            # TODO: need to think about how selection tools would work. These would likely be models/algorithms
            # for selection, not anything that provides access to cluster metadata (we are not running there)
            "4. INVESTIGATE: If you have Hub-level tools you MUST use them to verify assumptions\n"
            "   If you do not have tools, use any metadata or context provided to make a best assessment.\n"
            "5. FINAL PROPOSAL: Start your final response with 'FINAL PROPOSAL:'.\n"
            "6. STRUCTURED DATA: At the very end of your response, you MUST include a JSON code block:\n"
            "   - 'worker_id': The ID of the chosen cluster.\n"
            "   - 'status': Set to 'SELECTED' if a match is found, otherwise 'REJECTED'.\n"
            "   - 'reasoning': A concise explanation of your decision.\n"
            "\n"
            "Example format:\n"
            "FINAL PROPOSAL: Cluster alpha-4 is the winner because it is READY and has the exact Spack version requested.\n"
            "```json\n"
            "{\n"
            '  "worker_id": "alpha-4",\n'
            '  "status": "SELECTED",\n'
            '  "reasoning": "Best match and immediately available."\n'
            "}\n"
            "```"
        )
        if metadata:
            instruction += "\n" + metadata

        request = (
            f"ORIGINAL USER REQUEST: '{request}'\n\n"
            f"CLUSTER PROPOSALS TO EVALUATE:\n{json.dumps(proposals, indent=2)}"
        )
        return await self.deliberate(request, instructions, max_attempts=self.select_max_attempts)

    async def negotiate(self, request: str) -> str:
        """
        Negotiate a job means getting a request and asking worker
        children to generate proposals for work. Proposals can return different
        status: INCOMPATIBLE, READY, RESTRICTED, and BUSY. The last 2 require reasons.
        Since we are currently giving proposals for another LLM to access in selection,
        this is a reasonable start.
        """
        console.print(Panel(request, title="🤝 Negotiation Request", border_style="cyan"))

        # Note from vsoch: This prompt is REALLY important. Without, for example, 5, the agent will say
        # "this cluster probably has lammps installed" which is total garbage.
        system_context = self.build_system_context(["secretary"])
        instructions = (
            f"{system_context}\n"
            "### MANDATORY PROTOCOL ###\n"
            "1. ANALYZE: Review the user request against the 'Current Manifest Metadata' provided above.\n"
            "2. INVESTIGATE: You MUST make provider tool calls to get evidence of the system envirionment. "
            "   Format: CALL: provider.function(arg=val)\n"
            "3. NO GENERIC CHAT: Do not explain HOW to use software. Only determine IF this cluster "
            "is compatible and available.\n"
            "4. BE HONEST: If a resource is missing, broken, or the queue is too long, state that clearly.\n"
            "5. VERIFY: You MUST verify software is ALREADY installed and resources are sufficient.\n"
            "   A missing executable or failing discovery tool MUST deem the cluster insufficient.\n"
            "6. FINAL PROPOSAL: Start your final response with 'FINAL PROPOSAL:'. Provide your technical reasoning.\n"
            "7. STRUCTURED DATA: At the very end of your response, you MUST include a JSON code block "
            "containing the following keys:\n"
            "   - 'verdict': (READY, BUSY, or INCOMPATIBLE)\n"
            "   - 'reasoning': A brief summary of why this verdict was chosen.\n"
            "   - 'metrics': { 'queue_depth': int, 'ets_seconds': int } (Use 0 for READY, -1 if unknown)\n"
            "   - 'constraints': [list of strings] (Specific policy/resource limits)\n"
            "\n"
            "Example format:\n"
            "FINAL PROPOSAL: Technical explanation here...\n"
            "```json\n"
            "{\n"
            '  "verdict": "BUSY",\n'
            '  "reasoning": "Cluster has the requested A100 GPUs, but 4 jobs are ahead in the queue.",\n'
            '  "metrics": { "queue_depth": 4, "ets_seconds": 1200 },\n'
            '  "constraints": []\n'
            "}\n"
            "```"
        )
        # Require at least 1 call, and max 10 loops of thinking
        result = await self.deliberate(
            request, instructions, 1, max_attempts=self.negotiate_max_attempts
        )

        # Max attempts reached
        if "TIMEOUT" in result:
            timeout = json.dumps({"verdict": "UNKNOWN", "reason": "Deliberation timed out."})
            return f"FINAL PROPOSAL: Deliberation timed out.\n```json\n{json.dumps(timeout)}\n```"
        return result
