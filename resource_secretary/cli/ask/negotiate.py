import json
from dataclasses import dataclass

from fastmcp import Client
from rich.console import Console
from rich.panel import Panel

from resource_secretary.algorithm.select import get_selector
from resource_secretary.cli.ask.dispatch import handle_dispatch

console = Console()


@dataclass
class DispatchArgs:
    worker_id: str
    prompt: str
    url: str


async def handle_negotiate(args):
    """
    The full automated pipeline:
    1. Negotiate (Gather Proposals from Hub)
    2. Select (Run Pipeline)
    3. Dispatch (Execute on winning Worker)
    """
    prompt = args.prompt
    url = args.url
    strategies = args.select_strategies

    console.print(
        Panel.fit(
            f"🤝 [bold cyan]Resource Secretary: Negotiation & Dispatch[/bold cyan]\n"
            f"[dim]Request: {prompt}[/dim]",
            border_style="cyan",
        )
    )

    async with Client(url) as hub:

        # 1. Negotiation
        with console.status("[bold green]Broadcasting request to fleet..."):
            try:
                result = await hub.call_tool("negotiate_job", {"prompt": prompt})

                # Extract data (FastMCP structured content vs standard MCP text)
                data = getattr(result, "structured_content", None)
                if not data:
                    data = json.loads(result.content[0].text)

                proposals = data.get("proposals", {})
            except Exception as e:
                console.print(f"[bold red]Negotiation Error:[/bold red] Failed to contact Hub: {e}")
                return

        if not proposals:
            console.print("[bold red]Rejection:[/bold red] No workers are registered in the fleet.")
            return

        # 2. Selection
        console.print(f"🎯 [bold cyan]Selecting via Pipeline:[/bold cyan] {', '.join(strategies)}")

        # We wrap the strategies in the SelectorPipeline via the factory
        selector = get_selector(strategies)
        selection = await selector.select(prompt, proposals)

        # WOMP WOMP
        if selection.status == "REJECTED":
            console.print(f"❌ [bold red]Selection Failed:[/bold red] {selection.reasoning}")
            return

        worker_id = selection.worker_id
        console.print(f"✅ [bold green]Selected Worker:[/bold green] {worker_id}")
        console.print(f"📝 [dim]Decision: {selection.reasoning}[/dim]\n")

        # 3. Dispatch!
        dispatch_args = DispatchArgs(worker_id=worker_id, prompt=prompt, url=url)
        await handle_dispatch(dispatch_args)
