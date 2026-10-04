"""Who, how, when, why and with-what-else for every recorded event.

Spec FR-300 to FR-332, D-30 to D-38; research L-2 to L-6. Each decision below lives only here
(Principle IV): the environment variable, the actor grammar, the unknown actor, the login-name
rule, the timestamp format and the change-id rule.
"""

import getpass
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from troupe.errors import UsageError

ACTOR_ENV = "TROUPE_ACTOR"

type ActorKind = Literal["human", "agent", "unknown"]
type Via = Literal["import", "file", "cli"]

CLI_ACTOR_KINDS: tuple[ActorKind, ...] = ("human", "agent")


@dataclass(frozen=True)
class Actor:
    kind: ActorKind
    id: str | None


# Imports and file-originated events have no known author (FR-310).
UNKNOWN_ACTOR = Actor("unknown", None)


def login_name() -> str | None:
    """The login name of the user running the command, or None if it cannot be determined:
    null rather than a guess (spec D-34; research L-6 for why not `os.getlogin`)."""
    try:
        name = getpass.getuser()
    except (OSError, KeyError):
        return None
    return name or None


def actor_from_env(
    environ: Mapping[str, str], login: Callable[[], str | None] = login_name
) -> Actor:
    """A CLI command's actor from TROUPE_ACTOR (FR-320 to FR-322).

    Unset → a human with the login name. `human:<id>` / `agent:<id>` with a non-empty id → that
    actor, the id being everything after the first `:`, kept exactly (D-33). Anything else,
    including the empty string and an empty id, is a usage error (D-32).
    """
    if ACTOR_ENV not in environ:
        return Actor("human", login())
    value = environ[ACTOR_ENV]
    kind, separator, ident = value.partition(":")
    for allowed in CLI_ACTOR_KINDS:
        if separator and ident and kind == allowed:
            return Actor(allowed, ident)
    raise UsageError(f"{ACTOR_ENV}: {value!r} is not human:<id> or agent:<id>")


def format_at(moment: datetime) -> str:
    """RFC 3339 in UTC ending in `Z`, with microseconds (research L-4)."""
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def new_change_id() -> str:
    """Opaque and unique per recorded unit (spec D-37, research L-3)."""
    return str(uuid.uuid4())


@dataclass(frozen=True)
class Lineage:
    actor: Actor
    via: Via
    at: str
    reason: str | None
    change: str

    @classmethod
    def begin(cls, actor: Actor, via: Via, reason: str | None = None) -> "Lineage":
        """One Lineage per recorded unit (an import, a reconcile, or a set's own change): every
        event of the unit shares its change and at (FR-303, FR-305, D-30)."""
        return cls(actor, via, format_at(datetime.now(UTC)), reason, new_change_id())
