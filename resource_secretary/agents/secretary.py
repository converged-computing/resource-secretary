import json
import re
from typing import Any, Dict, List, Tuple

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

    def __init__(self, providers: List[Any]):
        self.providers = providers
        self.backend = get_backend()
        self.history = []
        self.provider_map = {p.name: p for p in self.providers}

    def build_system_context(self) -> str:
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
            tools = provider.discover_tools()

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
        """Executes the function and logs results to the worker console."""
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

    async def negotiate(self, request: str) -> str:
        """The reasoning loop with full transparency."""
        console.print(Panel(request, title="🤝 Negotiation Request", border_style="cyan"))

        # Note from vsoch: This prompt is REALLY important. WItout, for example, 5, the agent will say
        # "this cluster probably has lammps installed" which is total garbage.
        system_context = self.build_system_context()
        instructions = (
            f"{system_context}\n"
            "### MANDATORY PROTOCOL ###\n"
            "1. ANALYZE: Review the user request against the 'Current Manifest Metadata' provided above.\n"
            "2. INVESTIGATE: If the metadata is insufficient to answer (e.g., you need to check specific "
            "Spack builds, Flux queue depth, or GPU memory), YOU MUST call one or more discovery functions.\n"
            "   Format: CALL: provider.function(arg=val)\n"
            "3. NO GENERIC CHAT: Do not explain HOW to use software. Do not give tutorials. Your only "
            "job is to determine IF this specific cluster is compatible and available.\n"
            "4. BE HONEST: If a resource is missing, broken, or the queue is too long, state that clearly.\n"
            "5. VERIFY: You MUST verify that software is ALREADY installed and resources are sufficient.\n"
            "   A missing executable, means to assess, or resource MUST deem the cluster insufficient.\n"
            "   You are NOT ALLOWED to assume anything.\n"
            "6. FINAL PROPOSAL: Once you have all data, start your final response with 'FINAL PROPOSAL:'. "
            "Include your verdict (READY, BUSY, INCOMPATIBLE) and your technical reasoning."
        )
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

            if not calls:
                if "FINAL PROPOSAL:" in content:
                    console.print("[bold green]✅ Proposal Received.[/bold green]")
                    return content

                self.history.append(
                    {"role": "user", "content": "Please provide a FINAL PROPOSAL or a CALL:."}
                )
                continue

            # Execute calls
            obs = "OBSERVATIONS:\n"
            for p_name, f_name, args_str in calls:
                # Simple arg parser for text loop
                args = {}
                arg_pairs = re.findall(r'(\w+)\s*=\s*["\']?([^"\',]+)["\']?', args_str)
                for k, v in arg_pairs:
                    args[k] = v

                result = self.execute_call(p_name, f_name, args)
                obs += f"- {p_name}.{f_name}: {result}\n"

            self.history.append({"role": "user", "content": obs})

        return "Negotiation timed out."
