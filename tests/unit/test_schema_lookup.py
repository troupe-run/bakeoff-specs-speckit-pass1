"""Finding a value's subschema (spec FR-621, D-64; research U-5)."""

from typing import Any

from troupe.config.schema import is_uri, schema_child

URI = {"type": "string", "format": "uri"}


def test_child_by_properties() -> None:
    assert schema_child({"properties": {"a": URI}}, "a") == URI


def test_child_falls_back_to_additional_properties() -> None:
    schema = {"properties": {"a": {}}, "additionalProperties": URI}
    assert schema_child(schema, "b") == URI
    assert schema_child(schema, "a") == {}


def test_additional_properties_false_gives_none() -> None:
    assert schema_child({"additionalProperties": False}, "b") is None


def test_items_for_any_index() -> None:
    assert schema_child({"items": URI}, 0) == URI
    assert schema_child({"items": URI}, 7) == URI


def test_a_digit_key_of_a_mapping_uses_properties() -> None:
    assert schema_child({"properties": {"0": URI}, "items": {}}, "0") == URI


def test_other_keywords_are_not_followed() -> None:
    schema: dict[str, Any] = {
        "$defs": {"u": URI},
        "properties": {"r": {"$ref": "#/$defs/u"}, "all": {"allOf": [URI]}},
        "patternProperties": {"^p": URI},
        "prefixItems": [URI],
    }
    assert not is_uri(schema_child(schema, "r"))
    assert not is_uri(schema_child(schema, "all"))
    assert schema_child(schema, "pp") is None
    assert schema_child({"prefixItems": [URI]}, 0) is None


def test_none_and_non_objects_give_none() -> None:
    assert schema_child(None, "a") is None
    assert schema_child({"properties": {"a": True}}, "a") is None


def test_is_uri() -> None:
    assert is_uri(URI)
    assert not is_uri({"format": "email"})
    assert not is_uri(None)
