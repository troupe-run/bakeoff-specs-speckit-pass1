"""The theatre lock: one exclusive lock that every command holds from loading the files until it
has recorded its events (research S-3).

Holding it across load → compare → write → record is what makes every change recorded exactly
once (spec FR-130, FR-131): whichever process comes second finds the projection already matching
the files, so `watch` never records a `set`'s write-back again, and a hand edit is never recorded
by two processes.
"""

import fcntl
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from troupe.config.files import TROUPE_DIR, find_config
from troupe.config.store import STORE_FILENAME
from troupe.errors import LoadError

# Named after the store so it is grouped with the store's own files.
LOCK_FILENAME = STORE_FILENAME + ".lock"


@contextmanager
def theatre_lock(theatre: Path) -> Iterator[None]:
    path = theatre / TROUPE_DIR / LOCK_FILENAME
    if not path.parent.is_dir():
        find_config(theatre)  # nothing to lock: report the missing configuration instead
    try:
        try:
            fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
        except PermissionError:
            # flock works on a read-only descriptor too.
            fd = os.open(path, os.O_RDONLY)
    except OSError as error:
        raise LoadError(f"{path}: cannot open the lock file: {error.strerror}") from None
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)  # closing the descriptor releases the lock
