"""`config watch`: reconcile whenever a watched file changes (spec FR-100 to FR-106).

Changes are found by polling the exact bytes each file had when it was last parsed (research S-4).
Because the snapshot is what the last reconcile actually read, any change made after it, including
one made before the `watching` line was printed, makes the next poll differ: the line is a true
promise, and nothing depends on modification times or on how an editor saves.
"""

import threading
from collections.abc import Callable
from pathlib import Path

from troupe.config.fetch import FetchError
from troupe.config.files import CONFIG_NAMES, TROUPE_DIR
from troupe.config.loader import Loaded
from troupe.config.schema import SCHEMA_NAME
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
    reached by includes), plus both config-file names and the schema file, so creating or
    deleting any of them is seen."""
    snapshot: Snapshot = {
        path: source.text.encode("utf-8") for path, source in loaded.files.items()
    }
    # The schema decides which strings are literals, so it is watched too (step 7, research U-6).
    for name in (*CONFIG_NAMES, SCHEMA_NAME):
        path = (theatre / TROUPE_DIR / name).resolve()
        if path not in snapshot:
            snapshot[path] = _read(path)
    return snapshot


def changed(snapshot: Snapshot) -> bool:
    return any(_read(path) != data for path, data in snapshot.items())


def reread(snapshot: Snapshot) -> Snapshot:
    """The same files' current bytes: what the next change is compared against."""
    return {path: _read(path) for path in snapshot}


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
    which files matter is unknown until it loads again (research S-5). A remote include that
    cannot be fetched is reported the same way but retried only after a local file changes
    (step 7 D-65).
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
        except FetchError as error:
            # A URL that cannot be fetched is not polled (spec D-65): it is fetched again only
            # when a watched local file changes, so wait for the next change to the files as
            # they are now. The configuration's files are those of the last successful load.
            broken = False
            snapshot = reread(snapshot)
            if error.message != last_error:
                report(error.message)
                last_error = error.message
        except TroupeError as error:
            broken = True
            if error.message != last_error:
                report(error.message)
                last_error = error.message
        else:
            broken = False
            last_error = None
