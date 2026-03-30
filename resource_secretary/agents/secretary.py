import json
import re
from typing import Any, Dict, List

from rich import print
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from resource_secretary.agents.backends import get_backend

console = Console()


class SecretaryAgent:
    """
    The SecretaryAgent is the secretary for a cluster! It will discover resource providers,
    and then receive a job work request and ask the providers (functions calls) for more information.
    It will return (we hope) an honest response about the cluster ability to receive the job based
    on the user criteria.
    """

    def __init__(self, providers: List[Any] = None):
        self.providers = providers or []
        self.backend = get_backend()
        self.history = []
        self.provider_map = {p.name: p for p in self.providers}

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
            return f"Error: Provider '{provider_name}' not found."

        handler = provider.tools.get(func_name)
        if not handler:
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

    async def deliberate(self, request: str, instructions: str) -> str:
        """
        Deliberate can be a negotiation or a selection (prompt is an argument)
        """
        self.history = [
            {"role": "system", "content": instructions},
            {"role": "user", "content": f"Request: {request}"},
        ]

        for i in range(10):
            console.print(f"\n[bold magenta]Iteration {i}:[/bold magenta] Asking LLM...")

            raw_response = self.backend.generate_response(self.history)
            content, _ = self.backend.extract_content_and_calls(raw_response)

            console.print(Panel(content, title="🧠 LLM Thought/Action", border_style="green"))
            self.history.append(self.backend.format_assistant_message(raw_response))

            # Look for CALL: provider.function(args)
            calls = re.findall(r"CALL:\s*([\w\-]+)\.([\w\-]+)\((.*)\)", content)
            if calls:
                print(f"  Requested calls: {calls}")

            if not calls:
                if "FINAL PROPOSAL:" in content or "FINAL RESULT:" in content:
                    console.print("[bold green]✅ Proposal Received.[/bold green]")
                    return content

                self.history.append(
                    {"role": "user", "content": "Please provide a FINAL PROPOSAL or a CALL:."}
                )
                continue

            # These are function calls on the classes
            obs = "OBSERVATIONS:\n"
            for p_name, f_name, args_str in calls:
                args = {}
                arg_pairs = re.findall(r'(\w+)\s*=\s*["\']?([^"\',]+)["\']?', args_str)
                for k, v in arg_pairs:
                    args[k] = v

                result = self.execute_call(p_name, f_name, args)
                obs += f"- {p_name}.{f_name}: {result}\n"
                console.print(Panel(result, title=f"☎️ Call {f_name}: {args}", border_style="blue"))

            self.history.append({"role": "user", "content": obs})

        return "Deliberation timed out."

    async def submit(self, request: str) -> str:
        """
        Execution. Transforms a request into a concrete job,
        submits it, and verifies success.
        """
        system_context = self.build_system_context(["secretary", "dispatch"])
        instructions = (
            f"{system_context}\n"
            "### EXECUTION PROTOCOL ###\n"
            "1. TRANSLATE: Convert the user's natural language request into a concrete job specification.\n"
            "   (e.g., a Slurm sbatch script, a Flux job submit, or a Kubernetes manifest).\n"
            "2. PREPARE: Check for requirements. You MUST use CALL for submit, info, cancel, etc..\n"
            "       Format: CALL: provider.function(arg=val)\n"
            "3. NO GENERIC/INTERACTIVE CHAT: Do not explain HOW to use software. You CANNOT ask questions.\n"
            "4. SUBMIT: You MUST use the appropriate CALL to submit the job.\n"
            "5. BE HONEST: No faking submit or check. You MUST use CALL to submit, verify, and get info.\n"
            "6. FORBIDDEN: Under no conditions should you touch jobs not related to this task.\n"
            "7. VERIFY: After submission, YOU MUST call a status tool (e.g., squeue, flux jobs) "
            "   to verify the job is actually in the system and get a Job ID. You MUST report this status.\n"
            "8. NO GHOST JOBS: If you cannot verify a REAL job ID, you MUST report a failure.\n"
            "9. FINAL RESULT: You MUST start with 'FINAL RESULT:'. Detail what was done.\n"
            "   You are allowed to return a FINAL RESULT with FAILED if you are missing information\n"
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
        return await self.deliberate(f"EXECUTE REQUEST: {request}", instructions)

    async def select(self, request: str, proposals: Dict[str, Any]) -> str:
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
            "3. RANK: If multiple clusters are BUSY, choose the one with the lowest 'ets_seconds'.\n"
            # These aren't implemented yet, need to think about
            "4. INVESTIGATE: If you have Hub-level tools (provided in metadata), use them to verify "
            "external constraints like cost or site-wide priority.\n"
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
        request = (
            f"ORIGINAL USER REQUEST: '{request}'\n\n"
            f"CLUSTER PROPOSALS TO EVALUATE:\n{json.dumps(proposals, indent=2)}"
        )
        return await self.deliberate(request, instructions)

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
            "2. INVESTIGATE: If the metadata is insufficient to answer (e.g., check Spack builds, "
            "Flux queue depth, or GPU memory), YOU MUST call one or more discovery functions.\n"
            "   Format: CALL: provider.function(arg=val)\n"
            "3. NO GENERIC CHAT: Do not explain HOW to use software. Only determine IF this cluster "
            "is compatible and available.\n"
            "4. BE HONEST: If a resource is missing, broken, or the queue is too long, state that clearly.\n"
            "5. VERIFY: You MUST verify software is ALREADY installed and resources are sufficient.\n"
            "   A missing executable or failing discovery tool MUST deem the cluster insufficient.\n"
            "6. FINAL PROPOSAL: Start your final response with 'FINAL PROPOSAL:'. Provide your technical reasoning.\n"
            "7. STRUCTURED DATA: At the very end of your response, you MUST include a JSON code block "
            "containing the following keys:\n"
            "   - 'verdict': (READY, BUSY, RESTRICTED, or INCOMPATIBLE)\n"
            "   - 'reasoning': A brief summary of why this verdict was chosen.\n"
            "   - 'metrics': { 'queue_depth': int, 'ets_seconds': int } (Use 0 for READY, -1 if unknown)\n"
            "   - 'constraints': [list of strings] (Specific policy/resource limits for RESTRICTED)\n"
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
        return await self.deliberate(request, instructions)
