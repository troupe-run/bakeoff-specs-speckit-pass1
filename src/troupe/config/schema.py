"""The theatre's JSON Schema: where it is, how a value's subschema is found, and validation
(spec FR-620 to FR-634, D-64; research U-5, U-6).

A value's subschema is found from the root one segment at a time through `properties`,
`additionalProperties` and `items` only, as the contract says; a string whose subschema has
`"format": "uri"` is a literal, never an include.
"""

from typing import Any

type SubSchema = dict[str, Any] | None


def schema_child(sub: SubSchema, segment: str | int) -> SubSchema:
    """The subschema of a mapping key (`str`) or a list item (`int`) below `sub` (FR-621).

    No other keyword (`$ref`, `allOf`, `patternProperties`, `prefixItems`, …) is followed (D-64).
    """
    if sub is None:
        return None
    if isinstance(segment, int):
        return _object(sub.get("items"))
    properties = sub.get("properties")
    if isinstance(properties, dict) and segment in properties:
        return _object(properties[segment])
    return _object(sub.get("additionalProperties"))


def _object(value: object) -> SubSchema:
    return value if isinstance(value, dict) else None


def is_uri(sub: SubSchema) -> bool:
    """Whether a string with this subschema is a literal by schema (FR-620)."""
    return sub is not None and sub.get("format") == "uri"
