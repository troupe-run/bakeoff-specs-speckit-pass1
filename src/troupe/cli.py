"""Command-line entry point: `troupe config get|show|set|history|watch`."""

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from troupe.config import commands
from troupe.errors import TroupeError

PROG = "troupe"
THEATRE_ENV = "TROUPE_THEATRE"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=PROG, description="troupe AI orchestration tool")
    groups = parser.add_subparsers(dest="group", required=True, metavar="COMMAND")
    config = groups.add_parser("config", help="show, change and audit the theatre configuration")
    subcommands = config.add_subparsers(dest="subcommand", required=True, metavar="SUBCOMMAND")

    def add(name: str, help_text: str) -> argparse.ArgumentParser:
        sub = subcommands.add_parser(name, help=help_text)
        sub.add_argument(
            "--theatre",
            default=None,
            help=f"theatre directory (default: ${THEATRE_ENV}, else current directory)",
        )
        return sub

    add("get", "print a setting's value").add_argument("path", metavar="PATH")
    show = add("show", "print a setting, or a section as YAML")
    show.add_argument("path", metavar="PATH", nargs="?")
    show.add_argument("--sources", action="store_true", help="say which file each value is in")
    set_parser = add("set", "change a setting and write it back to its file")
    set_parser.add_argument("path", metavar="PATH")
    set_parser.add_argument("value", metavar="VALUE")
    add("history", "list configuration changes as JSON Lines").add_argument(
        "path", metavar="PATH", nargs="?"
    )
    add("watch", "record hand edits to the configuration as they happen")
    return parser


def theatre_display(theatre_arg: str | None) -> str:
    """The theatre as the user named it: `--theatre`, else $TROUPE_THEATRE, as given; else the
    absolute current directory, never a bare `.` (spec D-11)."""
    return theatre_arg or os.environ.get(THEATRE_ENV) or str(Path.cwd())


def error_line(message: str) -> str:
    return f"{PROG}: error: {message}"


def _announce(line: str) -> None:
    sys.stdout.buffer.write(line.encode("utf-8"))
    sys.stdout.flush()


def _report(message: str) -> None:
    print(error_line(message), file=sys.stderr, flush=True)


def run(argv: Sequence[str]) -> str:
    """Run a command and return its stdout; raises TroupeError on failure."""
    args = _parser().parse_args(argv)
    theatre = Path(args.theatre or os.environ.get(THEATRE_ENV) or ".")
    if args.subcommand == "watch":
        return commands.watch(theatre, theatre_display(args.theatre), _announce, _report)
    if args.subcommand == "get":
        return commands.get(theatre, args.path)
    if args.subcommand == "show":
        return commands.show(theatre, args.path, sources=args.sources)
    if args.subcommand == "set":
        return commands.set_value(theatre, args.path, args.value)
    return commands.history(theatre, args.path)


def main(argv: Sequence[str] | None = None) -> None:
    try:
        output = run(sys.argv[1:] if argv is None else argv)
    except TroupeError as error:
        print(error_line(error.message), file=sys.stderr)
        sys.exit(error.exit_code)
    sys.stdout.buffer.write(output.encode("utf-8"))
    sys.stdout.flush()
