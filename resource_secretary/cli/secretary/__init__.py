import argparse
import sys

from resource_secretary.cli.secretary.detect import handle_detect
from resource_secretary.cli.secretary.providers import handle_list_providers


def main():
    """
    Central entry point for the resource-secretary CLI.
    """
    parser = argparse.ArgumentParser(
        prog="resource-secretary", description="Agentic Resource Management and Negotiation Hub"
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Detect, with option for subcommand and specific name
    detect_parser = subparsers.add_parser("detect", help="Audit local system capabilities")
    detect_parser.add_argument(
        "category", nargs="?", help="Filter detection by category (e.g., 'software', 'workload')"
    )
    detect_parser.add_argument(
        "name",
        nargs="?",
        help="Filter detection by a specific provider name (e.g., 'spack', 'flux')",
    )
    detect_parser.add_argument(
        "--json", action="store_true", help="Output raw discovered data as JSON"
    )

    # providers
    providers = subparsers.add_parser(
        "providers", help="List all possible providers in the library"
    )
    providers.add_argument(
        "--simulated", action="store_true", help="Show simulated providers and descriptions"
    )

    args = parser.parse_args()

    if args.command == "detect":
        handle_detect(args)
    elif args.command == "providers":
        handle_list_providers(args)
    elif args.command is None:
        parser.print_help()
    else:
        print(f"Unknown command: {args.command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
