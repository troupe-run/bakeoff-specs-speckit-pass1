"""Which strings of a `set` VALUE are written tagged `!literal` (spec FR-640 to FR-643, D-68,
D-69; research U-8).

A string that would be read as an include is tagged, so it stays the string that was set, unless
the schema marks its path `format: uri` (it is a literal anyway) or `--include` asks for an
include. Each string is judged by its own path. This is the one place that decides; the renderer
only spells the tag.
"""

from dataclasses import replace

from troupe.config.includes import LITERAL_TAG, include_ref
from troupe.config.paths import ConfigPath, is_index
from troupe.config.scalars import NewNode
from troupe.config.schema import Schema, SubSchema, is_uri, schema_child
from troupe.errors import WriteRefused


def mark(value: NewNode, path: ConfigPath, schema: Schema | None, *, include: bool) -> NewNode:
    """`value` with every include-like string tagged as FR-640 to FR-643 require."""
    sub: SubSchema = None if schema is None else schema.document
    for segment in path.segments:
        sub = schema_child(sub, int(segment) if is_index(segment) else segment)
    return _mark(value, sub, path.dotted, include)


def _mark(node: NewNode, sub: SubSchema, where: str, include: bool) -> NewNode:
    if isinstance(node, list):
        return [
            _mark(item, schema_child(sub, index), f"{where}.{index}", include)
            for index, item in enumerate(node)
        ]
    if isinstance(node, dict):
        return {
            key: _mark(item, schema_child(sub, key), f"{where}.{key}", include)
            for key, item in node.items()
        }
    if include_ref(node.value) is None:
        return node
    if include:
        if is_uri(sub):
            # The schema says this value is a literal: it cannot be an include (spec D-68).
            raise WriteRefused(
                f"{where}: the schema marks it format: uri, so it cannot be an include; "
                "no file was changed"
            )
        return node
    return node if is_uri(sub) else replace(node, tag=LITERAL_TAG)
