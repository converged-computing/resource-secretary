from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from resource_secretary.providers import get_all_providers
from resource_secretary.providers.mock import get_all_mock_providers

console = Console()


def handle_list_providers(args):
    """
    Implementation of the 'providers' subcommand.
    Lists every provider registered in the library.
    """
    console.print(
        Panel.fit(
            "[bold cyan]🦊 Resource Secretary[/bold cyan]: [dim]Provider Catalog[/dim]",
            border_style="cyan",
        )
    )

    if args.simulated:
        catalog = get_all_mock_providers()
    else:
        catalog = get_all_providers()

    table = Table(
        title="Available Resource Providers", show_header=True, header_style="bold magenta"
    )
    table.add_column("Category", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Active", justify="center")
    table.add_column("Description", style="white")

    for category, instances in catalog.items():
        for inst in instances:
            # Probe now to see if the system currently supports this provider
            is_active = "[green]YES[/green]" if inst.probe() else "[red]NO[/red]"

            # Use the class docstring for the description
            doc = inst.__class__.__doc__ or "No description provided."
            description = doc.strip().split("\n")[0]

            table.add_row(category.upper(), inst.name.upper(), is_active, description)

    console.print(table)
    console.print(
        "[dim]Active = YES indicates the resource was discovered on your local system.[/dim]"
    )
