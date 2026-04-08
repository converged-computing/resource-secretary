import sys

from fastmcp import Client
from rich.console import Console
from rich.panel import Panel

import resource_secretary.utils as utils
from resource_secretary.algorithm.select import get_selector
from resource_secretary.cli.ask.negotiate import negotiate_job

console = Console()


async def handle_select(args):
    """
    Given one or more proposals, handle selection.
    """
    prompt = args.prompt
    url = args.url
    strategies = args.select_strategies

    console.print(
        Panel.fit(
            f"🤝 [bold cyan]Resource Secretary: Select[/bold cyan]\n"
            f"[dim]Request: {prompt}[/dim]",
            border_style="cyan",
        )
    )

    async with Client(url) as hub:

        # If we don't have a proposal file, we get them from server
        if not args.proposal_file:
            proposals = await negotiate_job(hub, prompt)
        else:
            proposals = utils.read_json(args.proposal_file)

        if not proposals:
            console.print(
                "[bold red]Error:[/bold red] You must provide a prompt to guide selection, or data for proposals."
            )
            return

        console.print(f"🎯 [bold cyan]Selecting via Pipeline:[/bold cyan] {', '.join(strategies)}")

        # We wrap the strategies in the SelectorPipeline via the factory
        selector = get_selector(strategies)
        selection = await selector.select(prompt, proposals)
        if selection.status == "REJECTED":
            console.print(f"❌ [bold red]Selection Failed:[/bold red] {selection.reasoning}")
            return

        worker_id = selection.worker_id
        console.print(f"✅ [bold green]Selected Worker:[/bold green] {worker_id}")
        console.print(f"📝 [dim]Decision: {selection.reasoning}[/dim]\n")

        # selection dataclass looks like this
        # worker_id: Optional[str] = None
        # status: SelectionStatus
        # reasoning: str
        # metadata: Dict[str, Any] = {}
        return selection
