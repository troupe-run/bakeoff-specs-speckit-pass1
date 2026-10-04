"""The event-sourced projection of the configuration, persisted under `.troupe/` (research R-4)."""

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

from eventsourcing.application import AggregateNotFoundError, Application
from eventsourcing.domain import Aggregate, event
from eventsourcing.persistence import PersistenceError

from troupe.config.files import TROUPE_DIR
from troupe.config.leaves import LeafEvent, Op
from troupe.config.lineage import Actor, ActorKind, Lineage, Via
from troupe.config.scalars import Scalar
from troupe.errors import LoadError, WriteRefused

STORE_FILENAME = "events.sqlite3"
CONFIG_AGGREGATE_ID = uuid5(NAMESPACE_URL, "troupe:theatre-config")


@dataclass(frozen=True)
class HistoryRecord:
    seq: int
    op: Op
    path: str
    old: Scalar
    new: Scalar
    lineage: Lineage


class TheatreConfig(Aggregate):
    """One aggregate per theatre; its leaf events form a single ordered stream."""

    @staticmethod
    def create_id() -> UUID:
        return CONFIG_AGGREGATE_ID

    def __init__(self) -> None:
        self.leaves: dict[str, Scalar] = {}
        self.log: list[HistoryRecord] = []

    # The lineage arguments are stored in each event and replayed with it, so lineage survives
    # restarts and never changes once recorded (spec FR-306, research L-1). They have no
    # defaults: stores recorded before step 4 are out of contract (research L-8).
    @event("LeafChanged")
    def change(
        self,
        op: Op,
        path: str,
        old: Scalar,
        new: Scalar,
        actor_kind: str,
        actor_id: str | None,
        via: str,
        at: str,
        reason: str | None,
        change: str,
    ) -> None:
        if op == "remove":
            self.leaves.pop(path, None)
        else:
            self.leaves[path] = new
        actor = Actor(cast(ActorKind, actor_kind), actor_id)
        lineage = Lineage(actor, cast(Via, via), at, reason, change)
        self.log.append(HistoryRecord(len(self.log) + 1, op, path, old, new, lineage))

    def apply(self, item: LeafEvent, lineage: Lineage) -> None:
        self.change(
            item.op,
            item.path,
            item.old,
            item.new,
            lineage.actor.kind,
            lineage.actor.id,
            lineage.via,
            lineage.at,
            lineage.reason,
            lineage.change,
        )


class _ConfigApplication(Application[UUID]):
    pass


_STORE_ERRORS = (sqlite3.Error, PersistenceError, OSError)


class ConfigStore:
    """The theatre's event store. Failures to use it are LoadErrors naming the store's file, so
    no command ever ends in a traceback (FR-007, FR-008)."""

    def __init__(self, theatre: Path) -> None:
        self.database = theatre / TROUPE_DIR / STORE_FILENAME
        with self._guard():
            self._app = _ConfigApplication(
                env={
                    "PERSISTENCE_MODULE": "eventsourcing.sqlite",
                    "SQLITE_DBNAME": str(self.database),
                }
            )

    @contextmanager
    def _guard(self) -> Iterator[None]:
        try:
            yield
        except _STORE_ERRORS as error:
            raise LoadError(f"{self.database}: cannot use the event store: {error}") from None

    def check_writable(self) -> None:
        """Refuse a change up front if its events could not be recorded afterwards."""
        directory = self.database.parent
        files = [self.database, *directory.glob(STORE_FILENAME + "-*")]
        if not os.access(directory, os.W_OK) or not all(os.access(f, os.W_OK) for f in files):
            raise WriteRefused(
                f"{self.database}: the event store is not writable; no file was changed"
            )

    def _get(self) -> TheatreConfig | None:
        try:
            with self._guard():
                aggregate: object = self._app.repository.get(CONFIG_AGGREGATE_ID)
        except AggregateNotFoundError:
            return None
        assert isinstance(aggregate, TheatreConfig)
        return aggregate

    def is_imported(self) -> bool:
        return self._get() is not None

    def import_leaves(self, leaves: dict[str, Scalar], lineage: Lineage) -> None:
        """Record the import, every event stamped with the one `lineage` (FR-305)."""
        aggregate = TheatreConfig()
        for path, value in leaves.items():
            aggregate.apply(LeafEvent("import", path, None, value), lineage)
        with self._guard():
            self._app.save(aggregate)

    def record(self, events: list[LeafEvent], lineage: Lineage) -> None:
        """Record one unit, every event stamped with the one `lineage` (FR-303, FR-305); a unit
        with no events leaves no trace."""
        if not events:
            return
        aggregate = self._get()
        assert aggregate is not None, "record() before import"
        for item in events:
            aggregate.apply(item, lineage)
        with self._guard():
            self._app.save(aggregate)

    def leaves(self) -> dict[str, Scalar]:
        """The projection: what reconcile compares the files against (spec D-10)."""
        aggregate = self._get()
        return {} if aggregate is None else dict(aggregate.leaves)

    def history(self) -> list[HistoryRecord]:
        aggregate = self._get()
        return [] if aggregate is None else list(aggregate.log)
