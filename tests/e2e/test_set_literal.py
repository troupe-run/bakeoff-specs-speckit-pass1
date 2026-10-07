"""`set` writes an include-like string as `!literal` unless the schema marks the path
`format: uri` or `--include` is given (spec US5, FR-640 to FR-646, D-67, D-68, D-69)."""

import json

from tests.conftest import Theatre, Web, assert_refused, assert_set

URI = {"type": "string", "format": "uri"}
URL = "https://example.com/guide"


def write_schema(theatre: Theatre, schema: object) -> None:
    theatre.write("troupe.schema.json", json.dumps(schema))


def test_replacing_with_a_url_writes_it_tagged(theatre: Theatre) -> None:
    assert_set(theatre, {"troupe.yml": "docs: old  # c\n"}, "docs", URL,
               {"troupe.yml": f"docs: !literal {URL} # c\n"})  # step 1 FR-036  # fmt: skip
    assert theatre.config("get", "docs").out == f"{URL}\n"


def test_format_uri_path_is_written_untagged(theatre: Theatre) -> None:
    write_schema(theatre, {"properties": {"api": {"properties": {"endpoint": URI}}}})
    assert_set(theatre, {"troupe.yml": "api:\n  endpoint: https://a.example/v1\n"},
               "api.endpoint", "https://a.example/v2",
               {"troupe.yml": "api:\n  endpoint: https://a.example/v2\n"})  # fmt: skip


def test_include_flag_writes_an_include(theatre: Theatre, web: Web) -> None:
    web.write("agents.yaml", "coder: {model: opus}\n")
    url = web.url("agents.yaml")
    assert_set(theatre, {"troupe.yml": "a: 1\n"}, "agents", url,
               {"troupe.yml": f"a: 1\nagents: {url}\n"}, options=("--include",))  # fmt: skip
    assert theatre.config("get", "agents.coder.model").out == "opus\n"


def test_include_flag_with_an_unloadable_target_is_refused(theatre: Theatre, web: Web) -> None:
    files = {"troupe.yml": "a: 1\n"}
    assert_refused(theatre, files, "b", web.url("status/404"), 3, "b", options=("--include",))
    assert_refused(theatre, files, "b", "file:missing.yaml", 3, "b", options=("--include",))


def test_a_file_string_is_tagged_too(theatre: Theatre) -> None:
    assert_set(theatre, {"troupe.yml": "a: 1\n"}, "notes", "file:notes.md",
               {"troupe.yml": "a: 1\nnotes: !literal file:notes.md\n"})  # fmt: skip


def test_other_strings_are_not_tagged(theatre: Theatre) -> None:
    assert_set(theatre, {"troupe.yml": "a: 1\n"}, "name", "coder",
               {"troupe.yml": "a: 1\nname: coder\n"})  # fmt: skip


def test_quoting_is_kept_after_the_tag(theatre: Theatre) -> None:
    assert_set(theatre, {"troupe.yml": 'docs: "old"\n'}, "docs", URL,
               {"troupe.yml": f'docs: !literal "{URL}"\n'})  # fmt: skip


def test_new_key_in_a_flow_mapping_is_tagged(theatre: Theatre) -> None:
    assert_set(theatre, {"troupe.yml": "a: {b: 1}\n"}, "a.u", URL,
               {"troupe.yml": f"a: {{b: 1, u: !literal {URL}}}\n"})  # fmt: skip
    assert theatre.config("get", "a.u").out == f"{URL}\n"


def test_appended_list_item_is_tagged(theatre: Theatre) -> None:
    assert_set(theatre, {"troupe.yml": "l:\n  - x\n"}, "l.1", URL,
               {"troupe.yml": f"l:\n  - x\n  - !literal {URL}\n"})  # fmt: skip


def test_new_override_under_an_include_is_tagged(theatre: Theatre) -> None:
    files = {"troupe.yml": "coder: file:c.yaml\n", "c.yaml": "model: opus\n"}
    expected = f"coder:\n  $ref: file:c.yaml\n  docs: !literal {URL}\n"
    assert_set(theatre, files, "coder.docs", URL, {"troupe.yml": expected})


def test_strings_inside_a_collection_value_are_tagged(theatre: Theatre) -> None:
    assert_set(theatre, {"troupe.yml": "a: 1\n"}, "b", f"{{u: {URL}, n: 1}}",
               {"troupe.yml": f"a: 1\nb:\n  u: !literal {URL}\n  n: 1\n"})  # fmt: skip
    assert theatre.config("get", "b.u").out == f"{URL}\n"


def test_collection_value_respects_nested_format_uri(theatre: Theatre) -> None:
    write_schema(theatre, {"properties": {"b": {"properties": {"u": URI}}}})
    assert_set(theatre, {"troupe.yml": "a: 1\n"}, "b", f"{{u: {URL}, v: {URL}}}",
               {"troupe.yml": f"a: 1\nb:\n  u: {URL}\n  v: !literal {URL}\n"})  # fmt: skip


def test_an_existing_tag_is_kept(theatre: Theatre) -> None:
    assert_set(theatre, {"troupe.yml": "docs: !literal https://a  # c\n"}, "docs", "plain",
               {"troupe.yml": "docs: !literal plain      # c\n"})  # FR-036  # fmt: skip


def test_an_existing_tag_is_not_doubled(theatre: Theatre) -> None:
    assert_set(theatre, {"troupe.yml": "docs: !literal https://a\n"}, "docs", URL,
               {"troupe.yml": f"docs: !literal {URL}\n"})  # fmt: skip


def test_include_flag_removes_an_existing_tag(theatre: Theatre, web: Web) -> None:
    web.write("d.md", "Guide\n")
    url = web.url("d.md")
    assert_set(theatre, {"troupe.yml": "docs: !literal https://a  # c\n"}, "docs", url,
               {"troupe.yml": f"docs: {url} # c\n"}, options=("--include",))  # FR-036  # fmt: skip
    assert theatre.config("get", "docs").out == "Guide\n"


def test_include_at_a_format_uri_path_is_refused(theatre: Theatre) -> None:
    write_schema(theatre, {"properties": {"u": URI}})
    assert_refused(theatre, {"troupe.yml": "u: https://a\n"}, "u", URL, 3, "u",
                   options=("--include",))  # fmt: skip


def test_include_flag_without_an_include_like_value_changes_nothing(theatre: Theatre) -> None:
    assert_set(theatre, {"troupe.yml": "a: 1\n"}, "a", "2", {"troupe.yml": "a: 2\n"},
               options=("--include",))  # fmt: skip


def test_a_multiline_url_string_is_a_tagged_literal_block(theatre: Theatre) -> None:
    assert_set(theatre, {"troupe.yml": "a: 1\n"}, "b", '"https://x\\ny"',
               {"troupe.yml": "a: 1\nb: !literal |-\n  https://x\n  y\n"})  # fmt: skip
    assert theatre.config("get", "b").out == "https://x\ny\n"


def test_events_have_no_tag(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "docs: old\n")
    assert theatre.config("set", "docs", URL).code == 0
    assert theatre.history()[-1] == {
        "seq": 2, "op": "set", "path": "docs", "old": "old", "new": URL,
    }  # fmt: skip


def test_text_include_target_is_written_untagged(theatre: Theatre) -> None:
    files = {"troupe.yml": "prompt: file:p.md\n", "p.md": "old\n"}
    assert_set(theatre, files, "prompt", URL, {"p.md": URL})


def test_expanding_an_alias_keeps_a_literal_tag(theatre: Theatre) -> None:
    text = f"d: &d\n  u: !literal {URL}\n  m: 1\ne: *d\n"
    expected = (
        f"d: &d\n  u: !literal {URL}\n  m: 1\ne:  # expanded from *d by troupe\n"
        f"  u: !literal {URL}\n  m: 2\n"
    )
    assert_set(theatre, {"troupe.yml": text}, "e.m", "2", {"troupe.yml": expected},
               options=("--expand-alias",))  # fmt: skip


def test_include_flag_removes_a_tag_on_a_literal_block(theatre: Theatre, web: Web) -> None:
    web.write("d.md", "Guide\n")
    url = web.url("d.md")
    assert_set(theatre, {"troupe.yml": "a: !literal |\n  old\n  text\nb: 1\n"}, "a", url,
               {"troupe.yml": f"a: |-\n  {url}\nb: 1\n"}, options=("--include",))  # fmt: skip
    # The block keeps its indicator (step 1 FR-030); its content is the include string.
    assert theatre.config("get", "a").out == "Guide\n"


def test_include_flag_removes_a_tag_on_an_empty_value(theatre: Theatre, web: Web) -> None:
    web.write("d.md", "Guide\n")
    url = web.url("d.md")
    assert_set(theatre, {"troupe.yml": "a: &k !literal\nb: 1\n"}, "a", url,
               {"troupe.yml": f"a: &k {url}\nb: 1\n"}, options=("--include",))  # fmt: skip


def test_an_empty_tagged_value_keeps_its_tag(theatre: Theatre) -> None:
    assert_set(theatre, {"troupe.yml": "a: !literal\nb: 1\n"}, "a", URL,
               {"troupe.yml": f"a: !literal {URL}\nb: 1\n"})  # fmt: skip


def test_an_empty_anchored_tagged_value_keeps_both(theatre: Theatre) -> None:
    assert_set(theatre, {"troupe.yml": "a: &k !literal\nb: 1\n"}, "a", "x",
               {"troupe.yml": "a: &k !literal x\nb: 1\n"})  # fmt: skip


def test_a_tagged_literal_block_keeps_its_tag(theatre: Theatre) -> None:
    assert_set(theatre, {"troupe.yml": "a: !literal |\n  old\n"}, "a", '"https://x\\ny\\n"',
               {"troupe.yml": "a: !literal |\n  https://x\n  y\n"})  # fmt: skip
