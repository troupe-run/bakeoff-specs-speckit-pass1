"""Which strings name includes: the one place that says so (spec FR-600, step 1 FR-010).

A string starting `file:` includes a local file; one starting `https://` or `http://` includes a
fetched document (step 7). Whether such a string at a given place really is an include, rather
than a literal, is the loader's decision (`_Loader.is_include`); this module only knows prefixes.
"""

from dataclasses import dataclass

FILE_PREFIX = "file:"
REMOTE_PREFIXES = ("https://", "http://")
LITERAL_TAG = "!literal"  # a string so tagged is never an include (spec FR-620)
REF_KEY = "$ref"  # the key of a mapping-form include (step 5 FR-400)


@dataclass(frozen=True)
class FileRef:
    """`file:<path>`: `path` is resolved relative to the including file."""

    path: str


@dataclass(frozen=True)
class UrlRef:
    """`https://…` or `http://…`: `url` is exactly as written."""

    url: str


def include_ref(value: object) -> FileRef | UrlRef | None:
    """What an include string names, or None if `value` is not one. Prefixes match exactly."""
    if not isinstance(value, str):
        return None
    if value.startswith(FILE_PREFIX):
        return FileRef(value[len(FILE_PREFIX) :])
    if value.startswith(REMOTE_PREFIXES):
        return UrlRef(value)
    return None
