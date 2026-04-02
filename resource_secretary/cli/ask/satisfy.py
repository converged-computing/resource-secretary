import json

from fastmcp import Client
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

import resource_secretary.utils as utils
from resource_secretary.algorithm.select.base import WorkerVerdict

console = Console()


def format_calls(calls_block):
    """
    Try to format calls.
    """
    content = ""
    try:
        calls = json.loads(utils.extract_code_block(calls_block))
    except:
        return content
    for call in calls:
        args = ", ".join([f"{x[0]}={x[1]}" for x in call["args"].items()])
        content += f"\n  {call['provider']}.{call['function']}({args})"
    return content


async def handle_satisfy(args):
    """
    Queries the fleet and displays detailed status without selecting or dispatching.
    """
    prompt = args.prompt
    url = args.url

    console.print(
        Panel.fit(
            f"🔍 [bold magenta]Satisfy Check (Dry Run)[/bold magenta]\n[dim]Prompt: {prompt}[/dim]",
            border_style="magenta",
        )
    )

    async with Client(url) as hub:
        with console.status("[bold green]Querying fleet Secretaries..."):
            try:
                result = await hub.call_tool("negotiate_job", {"prompt": prompt})
                # FastMCP returns structured_content, standard MCP returns content[0].text
                data = getattr(result, "structured_content", None)
                if not data:
                    data = json.loads(result.content[0].text)
            except Exception as e:
                console.print(f"[bold red]Error:[/bold red] Failed to communicate with Hub: {e}")
                return

        proposals = data.get("proposals", {})
        if not proposals:
            console.print("[yellow]No workers responded to the satisfy request.[/yellow]")
            return

        table = Table(title="Fleet Capability Audit", border_style="dim")
        table.add_column("Worker ID", style="magenta")
        table.add_column("Verdict", justify="center")
        table.add_column("Wait/ETS", justify="right")
        table.add_column("Technical Reasoning", style="white")

        for wid, response in proposals.items():
            inner_data = response.get("data", {})
            raw_proposal = ""

            if isinstance(inner_data, dict):
                raw_proposal = inner_data.get(
                    "proposal", inner_data.get("proposal_text", str(inner_data))
                )
            else:
                raw_proposal = str(inner_data)

            # Attempt to parse...
            verdict = "UNKNOWN"
            reasoning = raw_proposal
            ets_display = "N/A"

            try:
                # Were calls returned?
                calls = []
                if "CALLS" in raw_proposal:
                    raw_proposal, calls_block = raw_proposal.split("CALLS")
                    calls = format_calls(calls_block)

                parsed = parsed = json.loads(utils.extract_code_block(raw_proposal))

                verdict = parsed.get("verdict", "UNKNOWN")
                reasoning = parsed.get("reasoning", reasoning)

                metrics = parsed.get("metrics", {})
                ets = metrics.get("ets_seconds", -1)
                if ets == 0:
                    ets_display = "Immediate"
                elif ets > 0:
                    ets_display = f"{ets}s"

            except Exception:
                # Fallback to string matching if JSON parsing fails
                for v in [v.value for v in WorkerVerdict]:
                    if v in raw_proposal.upper():
                        verdict = v
                        break

            verdict_style = {
                "READY": "[bold green]READY[/bold green]",
                "BUSY": "[bold yellow]BUSY[/bold yellow]",
                "RESTRICTED": "[bold red]RESTRICTED[/bold red]",
                "INCOMPATIBLE": "[dim red]INCOMPATIBLE[/dim red]",
            }.get(verdict, f"[white]{verdict}[/white]")

            if calls:
                reasoning += f"\n{calls}"
            table.add_row(wid, verdict_style, ets_display, reasoning)

        console.print(table)
        console.print(f"\n[dim]Negotiation ID: {data.get('negotiation_id')}[/dim]")
