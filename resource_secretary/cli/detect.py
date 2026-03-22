import json
import sys

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from resource_secretary.providers import discover_providers

console = Console()


def handle_detect(args):
    """
    Implementation of the 'detect' subcommand.
    Supports filtering by category and specific provider name.
    """
    catalog = discover_providers()

    # 1. Apply Filtering Logic
    filtered_catalog = {}

    if args.category:
        category_key = args.category.lower()
        if category_key not in catalog:
            console.print(
                f"[bold red]Category '{category_key}' not found or no active providers discovered.[/bold red]"
            )
            return

        # Filter for the specific category
        instances = catalog[category_key]

        if args.name:
            provider_name = args.name.lower()
            # Find the specific instance in the category
            match = None
            for inst in instances:
                if inst.name.lower() == provider_name:
                    match = inst
                    break

            if not match:
                console.print(
                    f"[bold red]Provider '{provider_name}' not found in category '{category_key}'.[/bold red]"
                )
                return

            filtered_catalog[category_key] = [match]
        else:
            # Keep all in the category
            filtered_catalog[category_key] = instances
    else:
        # No filters, use the full catalog
        filtered_catalog = catalog

    # 2. JSON Output
    if args.json:
        output = {}
        for category, instances in filtered_catalog.items():
            output[category] = {}
            for inst in instances:
                tools_meta = inst.discover_tools()
                serializable_tools = {
                    name: {"description": info["description"], "parameters": info["parameters"]}
                    for name, info in tools_meta.items()
                }
                output[category][inst.name] = {
                    "metadata": inst.metadata,
                    "tools": serializable_tools,
                }
        print(json.dumps(output, indent=2))
        return

    # 3. Rich Output
    header_text = "[bold cyan]Resource Secretary[/bold cyan] - [dim]System Detect[/dim]"
    if args.category:
        header_text += f" [yellow]({args.category.capitalize()})[/yellow]"

    console.print(Panel.fit(header_text, border_style="cyan"))

    if not filtered_catalog:
        console.print("[bold red]No active providers discovered for the given filters.[/bold red]")
        return

    table = Table(title="Provider Manifest", show_header=True, header_style="bold magenta")
    table.add_column("Category", style="cyan")
    table.add_column("Provider", style="green")
    table.add_column("Metadata (Static)", style="white")

    for category, instances in filtered_catalog.items():
        for inst in instances:
            meta_json = json.dumps(inst.metadata, indent=2)
            meta_renderable = Syntax(meta_json, "json", theme="monokai", background_color="default")
            table.add_row(category.upper(), inst.name.upper(), meta_renderable)

    console.print(table)

    console.print("\n[bold yellow]Tool Discovery (Agent Visibility)[/bold yellow]")
    for category, instances in filtered_catalog.items():
        for inst in instances:
            tools = inst.discover_tools()
            if tools:
                tool_list = ", ".join([f"[blue]{t}[/blue]" for t in tools.keys()])
                console.print(f" • [bold]{inst.name}:[/bold] {tool_list}")
