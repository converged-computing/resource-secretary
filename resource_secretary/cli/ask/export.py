import json

from fastmcp import Client
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


async def handle_export(args):
    """
    Retrieves the internal 'Ground Truth' from mock providers across the fleet.
    """
    url = args.url

    console.print(
        Panel.fit(
            f"📡 [bold cyan]Fleet Metadata Export[/bold cyan]\n[dim]Target Hub: {url}[/dim]",
            border_style="cyan",
        )
    )

    async with Client(url) as hub:
        with console.status("[bold green]Extracting Ground Truth from workers..."):
            try:
                result = await hub.call_tool("export_fleet_truth", {})
                data = getattr(result, "structured_content", None)
                if not data:
                    data = json.loads(result.content[0].text)
            except Exception as e:
                console.print(f"[bold red]Error:[/bold red] Failed to communicate with Hub: {e}")
                return

        truth = data.get("ground_truth", {})
        if not truth:
            console.print("[yellow]No ground truth data returned from fleet.[/yellow]")
            return

        table = Table(title="Fleet Ground Truth Manifest", border_style="cyan")
        table.add_column("Worker ID", style="magenta")
        table.add_column("Provider", style="green")
        table.add_column("Internal State Summary", style="white")

        for wid, worker_truth in truth.items():
            # If the worker returned an error instead of truth data
            if (
                isinstance(worker_truth, dict)
                and "message" in worker_truth
                and worker_truth.get("type") == "error"
            ):
                table.add_row(wid, "[red]Error[/red]", worker_truth["message"])
                continue

            for provider_name, state in worker_truth.items():
                # Create a concise summary of the state for the table
                # TODO vsoch: think about more general approach once added providers
                summary = []
                if "version" in state:
                    summary.append(f"v{state['version']}")
                if "package_list" in state:
                    summary.append(f"{len(state['package_list'])} pkgs")
                if "nodes" in state:
                    summary.append(f"{state['nodes']} nodes")

                summary_text = ", ".join(summary) if summary else "Available"
                table.add_row(wid, provider_name, summary_text)

        console.print(table)

        # Optional: Save raw data to file (we will need for experiments)
        if args.output:
            try:
                with open(args.output, "w") as f:
                    json.dump(data, f, indent=4)
                console.print(
                    f"\n[bold green]Success:[/bold green] Raw metadata saved to [blue]{args.output}[/blue]"
                )
            except Exception as e:
                console.print(f"[bold red]Error:[/bold red] Failed to write output file: {e}")

        console.print(f"\n[dim]Export Timestamp: {data.get('timestamp')}[/dim]")
