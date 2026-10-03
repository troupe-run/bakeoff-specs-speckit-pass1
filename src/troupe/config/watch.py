"""`config watch`: reconcile whenever a watched file changes (spec FR-100 to FR-106).

Changes are found by polling the exact bytes each file had when it was last parsed (research S-4).
Because the snapshot is what the last reconcile actually read, any change made after it, including
one made before the `watching` line was printed, makes the next poll differ: the line is a true
promise, and nothing depends on modification times or on how an editor saves.
"""

import threading
from collections.abc import Callable
from pathlib import Path

from troupe.config.files import CONFIG_NAMES, TROUPE_DIR
from troupe.config.loader import Loaded
from troupe.errors import TroupeError

# Well inside the contract's 2 seconds, and cheap: configurations are small.
POLL_INTERVAL = 0.2

type Snapshot = dict[Path, bytes | None]


def _read(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


def snapshot_of(theatre: Path, loaded: Loaded) -> Snapshot:
    """The bytes of every file the configuration was loaded from (the main file and every file
    reached by includes), plus both config-file names, so creating or deleting either is seen."""
    snapshot: Snapshot = {
        path: source.text.encode("utf-8") for path, source in loaded.files.items()
    }
    for name in CONFIG_NAMES:
        path = (theatre / TROUPE_DIR / name).resolve()
        if path not in snapshot:
            snapshot[path] = _read(path)
    return snapshot


def changed(snapshot: Snapshot) -> bool:
    return any(_read(path) != data for path, data in snapshot.items())


def run_watch(
    theatre: Path,
    sync: Callable[[], Loaded],
    announce: Callable[[], None],
    stop: threading.Event,
    report: Callable[[str], None],
) -> None:
    """Reconcile (via `sync`), announce, then reconcile after every change until `stop` is set.

    A failure at start propagates (the command fails like any other). Later, a configuration
    that cannot be loaded is reported once per distinct message and retried on every poll, since
    which files matter is unknown until it loads again (research S-5).
    """
    snapshot = snapshot_of(theatre, sync())
    announce()
    broken = False
    last_error: str | None = None
    while not stop.wait(POLL_INTERVAL):
        if not broken and not changed(snapshot):
            continue
        try:
            snapshot = snapshot_of(theatre, sync())
        except TroupeError as error:
            broken = True
            if error.message != last_error:
                report(error.message)
                last_error = error.message
        else:
            broken = False
            last_error = None
