from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from resource_secretary.algorithm.select import STRATEGIES

console = Console()


def handle_list(args):
    """
    Implementation of 'resource-ask list <category>'
    """
    if args.category == "select":
        show_selection_algorithms()
    else:
        console.print(f"[red]Unknown list category: {args.category}[/red]")


def show_selection_algorithms():
    """
    Pretty print the selection algorithms in alphabetical order.
    """
    console.print(
        Panel.fit(
            "🎯 [bold cyan]Resource Secretary: Selection Algorithms[/bold cyan]\n"
            "[dim]Use these with the --select flag in the 'negotiate' command.[/dim]",
            border_style="cyan",
        )
    )

    table = Table(show_header=True, header_style="bold magenta", border_style="dim")
    table.add_column("Strategy Name", style="green", no_wrap=True)
    table.add_column("Tool Name", style="blue")
    table.add_column("Description", style="white")

    # Sort the strategies by their key (name) in alphabetical order
    sorted_strategy_names = sorted(STRATEGIES.keys())

    for name in sorted_strategy_names:
        cls = STRATEGIES[name]
        meta = getattr(cls, "metadata", {})

        tool_name = meta.get("name", "N/A")
        description = meta.get("description", "No description available.")

        table.add_row(name, tool_name, description)

    console.print(table)
    console.print("\n[bold yellow]Note on Pipeline Selection:[/bold yellow]")
    console.print("Strategies are executed in a fall-through pipeline.")
    console.print(
        'Example: [dim]resource-ask negotiate "..." --select agentic --select random[/dim]'
    )
    console.print("Default pipeline: [bold green]random -> soonest[/bold green]\n")
