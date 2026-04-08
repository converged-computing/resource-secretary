import argparse
import asyncio

from resource_secretary.cli.ask.export import handle_export
from resource_secretary.cli.ask.list import handle_list
from resource_secretary.cli.ask.negotiate import handle_negotiate
from resource_secretary.cli.ask.satisfy import handle_satisfy
from resource_secretary.cli.ask.select import handle_select


def main():
    parser = argparse.ArgumentParser(
        prog="resource-ask", description="Client interface for Resource Secretary"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # List something (e.g., selectors)
    list_p = subparsers.add_parser("list", help="List available components (e.g., 'select')")
    list_p.add_argument("category", choices=["select"], help="Category to list")

    # Satisfy
    satisfy_p = subparsers.add_parser("satisfy", help="Dry run: query cluster compatibility")

    # Export (e.g., simulation metadata)
    export_p = subparsers.add_parser("export", help="Export ground truth metadata from the fleet")
    export_p.add_argument("--output", help="Path to save the raw JSON output")

    select_p = subparsers.add_parser("select", help="Select for a prompt from proposals (in json)")
    select_p.add_argument(
        "--proposals", help="Path to json with proposals. Each should have data.proposal"
    )

    # Negotiate
    negotiate_p = subparsers.add_parser(
        "negotiate", help="Full lifecycle: negotiate, select, dispatch"
    )

    # Selection strategy
    negotiate_p.add_argument(
        "--select",
        action="append",
        dest="select_strategies",
        help="Append selection strategies. Default: ['random', 'soonest']",
    )
    for command in satisfy_p, negotiate_p, select_p:
        command.add_argument("prompt", help="Job description")
    for command in negotiate_p, export_p, satisfy_p:
        command.add_argument("--url", default="http://localhost:8000/mcp")

    args = parser.parse_args()

    if args.command == "list":
        handle_list(args)
    elif args.command == "select":
        handle_select(args)
    elif args.command == "satisfy":
        asyncio.run(handle_satisfy(args))
    elif args.command == "export":
        asyncio.run(handle_export(args))
    elif args.command == "negotiate":
        args.select_strategies = args.select_strategies or ["soonest", "random"]
        asyncio.run(handle_negotiate(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
