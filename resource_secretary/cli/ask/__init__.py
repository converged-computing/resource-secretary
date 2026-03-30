import argparse
import asyncio
import sys

from resource_secretary.cli.ask.list import handle_list
from resource_secretary.cli.ask.negotiate import handle_negotiate
from resource_secretary.cli.ask.satisfy import handle_satisfy


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
    satisfy_p.add_argument("prompt", help="Job description")
    satisfy_p.add_argument("--url", default="http://localhost:8000/mcp")

    # Negotiate
    negotiate_p = subparsers.add_parser(
        "negotiate", help="Full lifecycle: negotiate, select, dispatch"
    )
    negotiate_p.add_argument("prompt", help="Job description")
    negotiate_p.add_argument("--url", default="http://localhost:8000/mcp")
    negotiate_p.add_argument(
        "--select",
        action="append",
        dest="select_strategies",
        help="Append selection strategies. Default: ['random', 'soonest']",
    )

    args = parser.parse_args()

    if args.command == "list":
        handle_list(args)
    elif args.command == "satisfy":
        asyncio.run(handle_satisfy(args))
    elif args.command == "negotiate":
        if not args.select_strategies:
            args.select_strategies = ["random", "soonest"]
        asyncio.run(handle_negotiate(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
