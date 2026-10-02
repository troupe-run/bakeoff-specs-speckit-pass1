"""The event-sourced projection of the configuration, persisted under `.troupe/` (research R-4)."""

from dataclasses import dataclass
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from eventsourcing.application import AggregateNotFoundError, Application
from eventsourcing.domain import Aggregate, event

from troupe.config.files import TROUPE_DIR
from troupe.config.leaves import LeafEvent, Op
from troupe.config.scalars import Scalar

STORE_FILENAME = "events.sqlite3"
CONFIG_AGGREGATE_ID = uuid5(NAMESPACE_URL, "troupe:theatre-config")


@dataclass(frozen=True)
class HistoryRecord:
    seq: int
    op: Op
    path: str
    old: Scalar
    new: Scalar


class TheatreConfig(Aggregate):
    """One aggregate per theatre; its leaf events form a single ordered stream."""

    @staticmethod
    def create_id() -> UUID:
        return CONFIG_AGGREGATE_ID

    def __init__(self) -> None:
        self.leaves: dict[str, Scalar] = {}
        self.log: list[HistoryRecord] = []

    @event("LeafChanged")
    def change(self, op: Op, path: str, old: Scalar, new: Scalar) -> None:
        if op == "remove":
            self.leaves.pop(path, None)
        else:
            self.leaves[path] = new
        self.log.append(HistoryRecord(len(self.log) + 1, op, path, old, new))


class _ConfigApplication(Application[UUID]):
    pass


class ConfigStore:
    def __init__(self, theatre: Path) -> None:
        database = theatre / TROUPE_DIR / STORE_FILENAME
        self._app = _ConfigApplication(
            env={
                "PERSISTENCE_MODULE": "eventsourcing.sqlite",
                "SQLITE_DBNAME": str(database),
            }
        )

    def _get(self) -> TheatreConfig | None:
        try:
            aggregate: object = self._app.repository.get(CONFIG_AGGREGATE_ID)
        except AggregateNotFoundError:
            return None
        assert isinstance(aggregate, TheatreConfig)
        return aggregate

    def is_imported(self) -> bool:
        return self._get() is not None

    def import_leaves(self, leaves: dict[str, Scalar]) -> None:
        aggregate = TheatreConfig()
        for path, value in leaves.items():
            aggregate.change("import", path, None, value)
        self._app.save(aggregate)

    def record(self, events: list[LeafEvent]) -> None:
        if not events:
            return
        aggregate = self._get()
        assert aggregate is not None, "record() before import"
        for item in events:
            aggregate.change(item.op, item.path, item.old, item.new)
        self._app.save(aggregate)

    def history(self) -> list[HistoryRecord]:
        aggregate = self._get()
        return [] if aggregate is None else list(aggregate.log)
