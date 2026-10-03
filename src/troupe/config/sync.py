"""Reconcile: compare the files with the recorded configuration (spec FR-110 to FR-116)."""

from troupe.config.leaves import LeafEvent, diff_events, leaves
from troupe.config.loader import Loaded
from troupe.config.store import ConfigStore


def reconcile(loaded: Loaded, store: ConfigStore) -> list[LeafEvent]:
    """Record one `set`/`remove` event per leaf that differs between the files and the projection.

    Leaves are compared type-exactly, so formatting- and comment-only edits record nothing. Sets
    come in file order, removes in projection order (research S-1). The events are saved in one
    go, so they are recorded all together or not at all; no difference records nothing.
    """
    events = diff_events(store.leaves(), leaves(loaded.root))
    store.record(events)
    return events
