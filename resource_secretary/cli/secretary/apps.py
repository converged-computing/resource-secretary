import argparse
import json
import random
import sys

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from resource_secretary.apps import get_application, get_applications

console = Console()


def handle_apps(args):
    """
    List available scientific applications.
    """
    console.print(
        Panel.fit("[bold green]🧪 Application Catalog[/bold green]", border_style="green")
    )
    catalog = get_applications()

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Category", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Workloads", style="white")
    table.add_column("Modifiers", style="dim")

    for category, instances in catalog.items():
        category = " ".join([x.capitalize() for x in category.split("_")])
        for inst in instances:
            workloads = ", ".join(inst.workloads.keys())
            modifiers = ", ".join(inst.modifiers.keys())
            table.add_row(category, inst.name.upper(), workloads, modifiers)

    console.print(table)


def handle_prompt(args):
    """
    Generate and select prompts from the application matrix.
    """
    # Instantiate the app
    app = get_application(args.app)
    if not app:
        console.print(f"[red]Error:[/red] Application '{args.app}' not found.")
        sys.exit(1)

    # Load parameters (Default -> File -> CLI overrides)
    params = {"nodes": 5, "tasks": 320}  # Base defaults
    if args.file:
        with open(args.file, "r") as f:
            file_params = yaml.safe_load(f) if args.file.endswith(".yaml") else json.load(f)
            params.update(file_params)

    # Allow manual override of specific params via list of key=val
    if args.params:
        for p in args.params:
            k, v = p.split("=")
            params[k] = int(v) if v.isdigit() else v

    # Generate Matrix
    # We pass the workload and manager names specified in CLI
    level = args.level or ""
    prompts = app.get_prompt_matrix(
        workload=args.workload,
        manager=args.manager,
        modifiers=args.modifiers,
        filters=level,
        flatten=True,
        **params,
    )

    if args.show_count:
        if args.level:
            console.print(
                f"[yellow]There are {len(prompts)} generated prompts for filter: {args.level}.[/yellow]"
            )
        else:
            console.print(f"[yellow]There are {len(prompts)} generated prompts.[/yellow]")
        return

    if not prompts:
        console.print("[yellow]No prompts matched your filters.[/yellow]")
        return

    # Select Sample... clampysaurus!
    sample_size = min(args.count or len(prompts), len(prompts))
    selection = random.sample(prompts, sample_size)

    # 6. Output Results
    if args.output:
        with open(args.output, "w") as f:
            json.dump(selection, f, indent=4)
        console.print(f"[green]Saved {sample_size} prompts to {args.output}[/green]")
    else:
        for i, item in enumerate(selection):
            console.print(
                Panel(
                    f"[bold green]Truth:[/bold green] [dim]{item['command']}[/dim]\n"
                    f"[bold cyan]Prompt:[/bold cyan] {item['prompt']}\n"
                    f"[bold magenta]Style:[/bold magenta] {item['prompt_style']}",
                    title=f"Sample {i+1}/{sample_size}",
                    expand=False,
                )
            )
