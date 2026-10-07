"""The theatre's JSON Schema: where it is, how a value's subschema is found, and validation
(spec FR-620 to FR-634, D-64; research U-5, U-6).

A value's subschema is found from the root one segment at a time through `properties`,
`additionalProperties` and `items` only, as the contract says; a string whose subschema has
`"format": "uri"` is a literal, never an include.
"""

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, best_match

from troupe.config.files import TROUPE_DIR, read_source
from troupe.errors import LoadError

SCHEMA_NAME = "troupe.schema.json"  # under TROUPE_DIR (spec FR-630)
DIALECT = "https://json-schema.org/draft/2020-12/schema"
_REF_KEYWORDS = ("$ref", "$dynamicRef")

type SubSchema = dict[str, Any] | None


@dataclass(frozen=True)
class Schema:
    path: Path
    document: dict[str, Any]

    def validate(self, value: object) -> None:
        """Raise LoadError (exit 4) naming this file and a failing path if `value` — the loaded
        configuration — does not validate (FR-631). `format` is an annotation only (D-64), so no
        format checker is given."""
        error = best_match(Draft202012Validator(self.document).iter_errors(value))
        if error is None:
            return
        where = ".".join(str(part) for part in error.absolute_path) or "the top level"
        raise LoadError(f"{self.path}: {where}: {error.message}")


def schema_path(theatre: Path) -> Path:
    return theatre / TROUPE_DIR / SCHEMA_NAME


def load_schema(theatre: Path) -> Schema | None:
    """The theatre's schema, or None when it has none. A schema that cannot be used makes the
    configuration unloadable: exit 4 naming the schema file (FR-630)."""
    path = schema_path(theatre)
    if not path.exists():
        return None
    path = path.resolve()
    source = read_source(path)
    try:
        document = json.loads(source.text)
    except json.JSONDecodeError as error:
        raise LoadError(f"{path}: invalid JSON: {error}") from None
    if not isinstance(document, dict):
        raise LoadError(f"{path}: a schema must be a JSON object")
    dialect = document.get("$schema", DIALECT)
    if dialect != DIALECT:
        raise LoadError(f"{path}: $schema must be JSON Schema 2020-12 ({DIALECT}), not {dialect!r}")
    try:
        Draft202012Validator.check_schema(document)
    except SchemaError as error:
        raise LoadError(f"{path}: not a valid JSON Schema: {error.message}") from None
    for reference in _references(document):
        if not reference.startswith("#"):
            # The schema never causes a fetch or a read elsewhere (spec D-64).
            raise LoadError(f"{path}: $ref {reference!r} points outside the schema")
    return Schema(path, document)


def _references(value: object) -> Iterator[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _REF_KEYWORDS and isinstance(item, str):
                yield item
            else:
                yield from _references(item)
    elif isinstance(value, list):
        for item in value:
            yield from _references(item)


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
