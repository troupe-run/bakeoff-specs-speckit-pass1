"""Configuration paths: keys separated by `.`; an all-digit segment indexes a list."""

from dataclasses import dataclass

from troupe.errors import UsageError

SEPARATOR = "."


def is_index(segment: str) -> bool:
    """True when the segment indexes a list (ASCII digits only)."""
    return segment.isascii() and segment.isdigit()


@dataclass(frozen=True)
class ConfigPath:
    segments: tuple[str, ...]

    @classmethod
    def parse(cls, text: str) -> "ConfigPath":
        segments = tuple(text.split(SEPARATOR))
        if not text or any(segment == "" for segment in segments):
            raise UsageError(f"invalid path {text!r}: path segments must not be empty")
        return cls(segments)

    @property
    def dotted(self) -> str:
        return SEPARATOR.join(self.segments)

    def child(self, segment: str) -> "ConfigPath":
        return ConfigPath((*self.segments, segment))

    def is_within(self, other: "ConfigPath") -> bool:
        """True when this path equals `other` or lies below it."""
        return self.segments[: len(other.segments)] == other.segments

    def __str__(self) -> str:
        return self.dotted


def dotted_is_within(path: str, prefix: str) -> bool:
    """String form of `is_within`: `path` equals `prefix` or starts with `prefix.`."""
    return path == prefix or path.startswith(prefix + SEPARATOR)
