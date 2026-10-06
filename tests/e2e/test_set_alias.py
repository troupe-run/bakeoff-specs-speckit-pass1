"""YAML anchors and aliases: a value is changed at its anchor, never silently through an alias;
`set --expand-alias` gives one alias its own copy first (step 6, bug yaml-alias-set)."""

from tests.conftest import Theatre, assert_refused, assert_set, set_ok

FLAG = ("--expand-alias",)
SHARED = "defaults: &d\n  model: opus\ncoder:\n  settings: *d\nreviewer:\n  settings: *d\n"


def _get(theatre: Theatre, path: str) -> str:
    result = theatre.config("get", path)
    assert result.code == 0, result
    return result.out


def test_setting_through_an_alias_is_refused(theatre: Theatre) -> None:
    # The reported bug: this used to change `defaults` and `reviewer` too.
    files = {"troupe.yml": SHARED}
    assert_refused(theatre, files, "coder.settings.model", "sonnet", 3, "--expand-alias")


def test_a_new_key_through_an_alias_is_refused(theatre: Theatre) -> None:
    files = {"troupe.yml": SHARED}
    assert_refused(theatre, files, "coder.settings.temperature", "0.2", 3, "--expand-alias")


def test_setting_at_the_anchor_changes_every_alias(theatre: Theatre) -> None:
    files = {"troupe.yml": SHARED}
    expected = {"troupe.yml": SHARED.replace("opus", "sonnet")}
    assert_set(theatre, files, "defaults.model", "sonnet", expected)
    assert _get(theatre, "coder.settings.model") == "sonnet\n"
    assert _get(theatre, "reviewer.settings.model") == "sonnet\n"


def test_expand_alias_gives_the_alias_its_own_copy(theatre: Theatre) -> None:
    files = {"troupe.yml": SHARED}
    expected = {
        "troupe.yml": (
            "defaults: &d\n  model: opus\n"
            "coder:\n  settings:  # expanded from *d by troupe\n    model: sonnet\n"
            "reviewer:\n  settings: *d\n"
        )
    }
    assert_set(theatre, files, "coder.settings.model", "sonnet", expected, FLAG)
    assert _get(theatre, "defaults.model") == "opus\n"
    assert _get(theatre, "reviewer.settings.model") == "opus\n"
    changes = [e for e in theatre.history() if e["op"] == "set"]
    assert changes == [
        {"seq": changes[0]["seq"], "op": "set", "path": "coder.settings.model"}
        | {"old": "opus", "new": "sonnet"}
    ]


def test_expand_alias_adds_a_new_key_to_the_copy(theatre: Theatre) -> None:
    files = {"troupe.yml": SHARED}
    expected = {
        "troupe.yml": SHARED.replace(
            "  settings: *d\nreviewer",
            "  settings:  # expanded from *d by troupe\n    model: opus\n"
            "    temperature: 0.2\nreviewer",
        )
    }
    assert_set(theatre, files, "coder.settings.temperature", "0.2", expected, FLAG)


def test_expand_alias_in_a_list_item(theatre: Theatre) -> None:
    main = "base: &b\n  model: opus\nagents:\n  - *b\n  - *b\n"
    expected = main.replace(
        "  - *b\n  - *b\n", "  -  # expanded from *b by troupe\n    model: x\n  - *b\n"
    )
    assert_set(theatre, {"troupe.yml": main}, "agents.0.model", "x", {"troupe.yml": expected}, FLAG)


def test_expand_alias_without_an_alias_is_a_plain_set(theatre: Theatre) -> None:
    files = {"troupe.yml": SHARED}
    expected = {"troupe.yml": SHARED.replace("opus", "haiku")}
    assert_set(theatre, files, "defaults.model", "haiku", expected, FLAG)


def test_an_anchored_scalar_keeps_its_anchor(theatre: Theatre) -> None:
    main = "limit: &n 5\nother: *n\n"
    assert_set(
        theatre, {"troupe.yml": main}, "limit", "6", {"troupe.yml": "limit: &n 6\nother: *n\n"}
    )
    assert _get(theatre, "other") == "6\n"


def test_replacing_an_anchored_section_keeps_its_anchor(theatre: Theatre) -> None:
    files = {"troupe.yml": SHARED}
    expected = {"troupe.yml": SHARED.replace("  model: opus\n", "  model: x\n  t: 1\n")}
    assert_set(theatre, files, "defaults", "{model: x, t: 1}", expected)
    assert _get(theatre, "reviewer.settings.t") == "1\n"


def test_replacing_the_alias_itself_changes_only_it(theatre: Theatre) -> None:
    files = {"troupe.yml": SHARED}
    expected = {
        "troupe.yml": SHARED.replace("  settings: *d\nreviewer", "  settings: none\nreviewer")
    }
    assert_set(theatre, files, "coder.settings", "none", expected)
    assert _get(theatre, "reviewer.settings.model") == "opus\n"


def test_merge_keys_are_never_written(theatre: Theatre) -> None:
    main = "base: &b\n  model: opus\ncoder:\n  <<: *b\n  t: 1\n"
    assert_refused(theatre, {"troupe.yml": main}, "coder.<<.model", "x", 3, "<<", FLAG)
    assert_refused(theatre, {"troupe.yml": main}, "coder.<<", "x", 3, "<<")
    assert_refused(theatre, {"troupe.yml": main}, "reviewer.<<", "x", 3, "<<")


def test_an_alias_in_a_flow_collection_is_not_expanded(theatre: Theatre) -> None:
    main = "base: &b\n  model: opus\ncoder: {settings: *b}\n"
    assert_refused(theatre, {"troupe.yml": main}, "coder.settings.model", "x", 3, "*b", FLAG)


def test_refusal_without_the_flag_then_success_with_it(theatre: Theatre) -> None:
    theatre.write("troupe.yml", SHARED)
    refused = theatre.config("set", "coder.settings.model", "sonnet")
    assert refused.code == 3 and "--expand-alias" in refused.err
    set_ok(theatre, "coder.settings.model", "sonnet", *FLAG)
    assert _get(theatre, "coder.settings.model") == "sonnet\n"
