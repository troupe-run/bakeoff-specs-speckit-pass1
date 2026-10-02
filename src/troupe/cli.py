"""Command-line entry point: `troupe config show|set|history`."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from troupe.config import commands
from troupe.errors import TroupeError

PROG = "troupe"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=PROG, description="troupe AI orchestration tool")
    groups = parser.add_subparsers(dest="group", required=True, metavar="COMMAND")
    config = groups.add_parser("config", help="show, change and audit the theatre configuration")
    subcommands = config.add_subparsers(dest="subcommand", required=True, metavar="SUBCOMMAND")

    def add(name: str, help_text: str) -> argparse.ArgumentParser:
        sub = subcommands.add_parser(name, help=help_text)
        sub.add_argument(
            "--theatre",
            type=Path,
            default=Path("."),
            help="theatre directory (default: current directory)",
        )
        return sub

    add("show", "print a setting's value").add_argument("path", metavar="PATH")
    set_parser = add("set", "change a setting and write it back to its file")
    set_parser.add_argument("path", metavar="PATH")
    set_parser.add_argument("value", metavar="VALUE")
    add("history", "list configuration changes as JSON Lines").add_argument(
        "path", metavar="PATH", nargs="?"
    )
    return parser


def run(argv: Sequence[str]) -> str:
    """Run a command and return its stdout; raises TroupeError on failure."""
    args = _parser().parse_args(argv)
    theatre: Path = args.theatre
    if args.subcommand == "show":
        return commands.show(theatre, args.path)
    if args.subcommand == "set":
        return commands.set_value(theatre, args.path, args.value)
    return commands.history(theatre, args.path)


def main(argv: Sequence[str] | None = None) -> None:
    try:
        output = run(sys.argv[1:] if argv is None else argv)
    except TroupeError as error:
        print(f"{PROG}: error: {error.message}", file=sys.stderr)
        sys.exit(error.exit_code)
    sys.stdout.buffer.write(output.encode("utf-8"))
    sys.stdout.flush()
