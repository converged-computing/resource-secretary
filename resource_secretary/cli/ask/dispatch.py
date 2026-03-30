import json

from fastmcp import Client
from rich.console import Console
from rich.panel import Panel

console = Console()


async def handle_dispatch(args):
    """
    Stand-alone dispatch to a known worker.
    """
    worker_id = args.worker_id
    prompt = args.prompt
    url = args.url

    console.print(f"🚀 [bold yellow]Dispatching to {worker_id}...[/bold yellow]")

    async with Client(url) as hub:
        result = await hub.call_tool("dispatch_job", {"worker_id": worker_id, "prompt": prompt})

        # Check if the hub returned a raw string or dict
        data = json.loads(result.content[0].text)
        receipt = data.get("receipt", {})

        if receipt.get("status") == "SUCCESS":
            console.print(
                Panel(
                    f"[bold green]Job Successfully Submitted![/bold green]\n"
                    f"Worker: {worker_id}\n"
                    f"Job ID: [cyan]{receipt.get('job_id')}[/cyan]\n"
                    f"Command: [dim]{receipt.get('spec')}[/dim]",
                    title="Execution Receipt",
                    border_style="green",
                )
            )
        else:
            console.print(
                Panel(
                    f"[bold red]Dispatch Failed[/bold red]\n{receipt.get('reasoning')}",
                    title="Error",
                    border_style="red",
                )
            )
