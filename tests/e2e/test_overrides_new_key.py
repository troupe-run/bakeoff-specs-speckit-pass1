"""A new key under included content is written as an override in the including file (spec US1,
FR-420 to FR-427, D-40, D-41, D-45, D-47, D-48)."""

from tests.conftest import Theatre, assert_refused, assert_set

CODER = {"agents/coder.yaml": "model: sonnet\n"}


def test_contract_conversion_example(theatre: Theatre) -> None:
    files = {"troupe.yml": "coder: file:agents/coder.yaml  # c\n", **CODER}
    expected = "coder:  # c\n  $ref: file:agents/coder.yaml\n  temperature: 0.3\n"
    assert_set(theatre, files, "coder.temperature", "0.3", {"troupe.yml": expected})


def test_nested_include_is_converted_at_the_files_indentation(theatre: Theatre) -> None:
    files = {"troupe.yml": "agents:\n  coder: file:agents/coder.yaml  # c\n", **CODER}
    expected = "agents:\n  coder:  # c\n    $ref: file:agents/coder.yaml\n    temperature: 0.3\n"
    assert_set(theatre, files, "agents.coder.temperature", "0.3", {"troupe.yml": expected})
    assert theatre.config("get", "agents.coder.model").out == "sonnet\n"


def test_existing_mapping_form_gets_the_key_after_its_last_override(theatre: Theatre) -> None:
    main = "agents:\n  coder:\n    $ref: file:agents/coder.yaml\n    model: opus\nnext: 1\n"
    files = {"troupe.yml": main, **CODER}
    expected = main.replace("opus\n", "opus\n    temperature: 0.3\n")
    assert_set(theatre, files, "agents.coder.temperature", "0.3", {"troupe.yml": expected})


def test_missing_intermediate_mappings_are_created_in_the_override(theatre: Theatre) -> None:
    files = {
        "troupe.yml": "agents:\n  coder: file:agents/coder.yaml\n",
        "agents/coder.yaml": "limits: {retries: 2}\n",
    }
    expected = (
        "agents:\n  coder:\n    $ref: file:agents/coder.yaml\n    limits:\n      timeout: 30\n"
    )
    assert_set(theatre, files, "agents.coder.limits.timeout", "30", {"troupe.yml": expected})
    assert theatre.config("get", "agents.coder.limits.retries").out == "2\n"


def test_flow_include_becomes_a_flow_mapping(theatre: Theatre) -> None:
    files = {"troupe.yml": "agents: {coder: file:agents/coder.yaml}\n", **CODER}
    expected = "agents: {coder: {$ref: file:agents/coder.yaml, temperature: 0.3}}\n"
    assert_set(theatre, files, "agents.coder.temperature", "0.3", {"troupe.yml": expected})


def test_one_set_event_for_the_new_leaf(theatre: Theatre) -> None:
    theatre.write("troupe.yml", "agents:\n  coder: file:agents/coder.yaml\n")
    theatre.write("agents/coder.yaml", "model: sonnet\n")
    assert theatre.config("set", "agents.coder.temperature", "0.3").code == 0
    events = [e for e in theatre.events() if e["op"] != "import"]
    assert [(e["op"], e["path"], e["old"], e["new"], e["via"]) for e in events] == [
        ("set", "agents.coder.temperature", None, 0.3, "cli")
    ]


def test_include_without_comment(theatre: Theatre) -> None:
    files = {"troupe.yml": "coder: file:c.yaml\n", "c.yaml": "a: 1\n"}
    assert_set(
        theatre, files, "coder.t", "1", {"troupe.yml": "coder:\n  $ref: file:c.yaml\n  t: 1\n"}
    )


def test_quoted_include_string_keeps_its_quotes(theatre: Theatre) -> None:
    files = {"troupe.yml": 'coder: "file:c.yaml"\n', "c.yaml": "a: 1\n"}
    expected = 'coder:\n  $ref: "file:c.yaml"\n  t: 1\n'
    assert_set(theatre, files, "coder.t", "1", {"troupe.yml": expected})


def test_file_indentation_of_4(theatre: Theatre) -> None:
    files = {"troupe.yml": "agents:\n    coder: file:c.yaml\n", "c.yaml": "a: 1\n"}
    expected = "agents:\n    coder:\n        $ref: file:c.yaml\n        t: 1\n"
    assert_set(theatre, files, "agents.coder.t", "1", {"troupe.yml": expected})


def test_crlf_including_file_gets_crlf_lines(theatre: Theatre) -> None:
    files = {"troupe.yml": "coder: file:c.yaml\r\n", "c.yaml": "a: 1\n"}
    expected = "coder:\r\n  $ref: file:c.yaml\r\n  t: 1\r\n"
    assert_set(theatre, files, "coder.t", "1", {"troupe.yml": expected})


def test_existing_override_mapping_is_reused(theatre: Theatre) -> None:
    main = "coder:\n  $ref: file:c.yaml\n  limits:\n    timeout: 30\n"
    files = {"troupe.yml": main, "c.yaml": "limits:\n  retries: 2\n"}
    expected = main + "    backoff: 2\n"
    assert_set(theatre, files, "coder.limits.backoff", "2", {"troupe.yml": expected})


def test_new_key_deeper_under_a_merged_mapping_goes_into_the_override(theatre: Theatre) -> None:
    main = "coder:\n  $ref: file:c.yaml\n  limits:\n    timeout: 30\n"
    files = {"troupe.yml": main, "c.yaml": "limits:\n  retries: 2\n"}
    expected = main + "    x:\n      y: 1\n"
    assert_set(theatre, files, "coder.limits.x.y", "1", {"troupe.yml": expected})


def test_new_sibling_after_a_mapping_form_include_goes_below_the_whole_mapping(
    theatre: Theatre,
) -> None:
    main = "agents:\n  coder:\n    $ref: file:c.yaml\n    model: x\nnext: 1\n"
    files = {"troupe.yml": main, "c.yaml": "a: 1\n"}
    expected = main.replace("model: x\n", "model: x\n  reviewer: y\n")
    assert_set(theatre, files, "agents.reviewer", "y", {"troupe.yml": expected})


def test_nested_includes_write_in_the_nearest_including_file(theatre: Theatre) -> None:
    files = {
        "troupe.yml": "agents:\n  coder: file:coder.yaml\n",
        "coder.yaml": "model: file:model.yaml\n",
        "model.yaml": "name: m\n",
    }
    expected = "model:\n  $ref: file:model.yaml\n  temp: 1\n"
    assert_set(theatre, files, "agents.coder.model.temp", "1", {"coder.yaml": expected})


def test_new_key_below_a_nested_merged_include_goes_to_its_nearest_including_file(
    theatre: Theatre,
) -> None:
    files = {
        "troupe.yml": "coder:\n  $ref: file:coder.yaml\n  model:\n    x: 1\n",
        "coder.yaml": "model: file:model.yaml\n",
        "model.yaml": "a:\n  c: 2\n",
    }
    expected = "model:\n  $ref: file:model.yaml\n  a:\n    d: 3\n"
    assert_set(theatre, files, "coder.model.a.d", "3", {"coder.yaml": expected})
    assert theatre.config("get", "coder.model.a.c").out == "2\n"


def test_ancestor_written_in_an_included_file_goes_one_level_out(theatre: Theatre) -> None:
    files = {
        "troupe.yml": "agents:\n  coder: file:coder.yaml\n",
        "coder.yaml": "model:\n  $ref: file:model.yaml\n  a:\n    b: 1\n",
        "model.yaml": "a:\n  c: 2\n",
    }
    expected = "agents:\n  coder:\n    $ref: file:coder.yaml\n    model:\n      a:\n        d: 3\n"
    assert_set(theatre, files, "agents.coder.model.a.d", "3", {"troupe.yml": expected})
    assert theatre.config("get", "agents.coder.model.a.b").out == "1\n"
    assert theatre.config("get", "agents.coder.model.a.c").out == "2\n"


def test_list_item_include_converted_in_place(theatre: Theatre) -> None:
    files = {"troupe.yml": "agents:\n  - file:a.yaml  # c\n", "a.yaml": "model: m\n"}
    expected = "agents:\n  - $ref: file:a.yaml  # c\n    temperature: 0.3\n"
    assert_set(theatre, files, "agents.0.temperature", "0.3", {"troupe.yml": expected})


def test_override_position_that_is_an_include_is_refused(theatre: Theatre) -> None:
    files = {
        "troupe.yml": "coder:\n  $ref: file:c.yaml\n  limits: file:l.yaml\n",
        "c.yaml": "limits:\n  retries: 2\n",
        "l.yaml": "timeout: 30\n",
    }
    assert_refused(theatre, files, "coder.limits.x", "1", 3, "is an include")
    assert "coder.limits.x" in theatre.config("set", "coder.limits.x", "1").err  # SC-404


def test_file_included_twice_gets_the_override_only_at_its_site(theatre: Theatre) -> None:
    files = {"troupe.yml": "a: file:common.yaml\nb: file:common.yaml\n", "common.yaml": "x: 1\n"}
    expected = "a:\n  $ref: file:common.yaml\n  y: 2\nb: file:common.yaml\n"
    assert_set(theatre, files, "a.y", "2", {"troupe.yml": expected})
    result = theatre.config("get", "b.y")
    assert result.code == 5, result


def test_new_key_with_ancestor_in_the_main_file_is_written_there(theatre: Theatre) -> None:
    files = {"troupe.yml": "a:\n  b: 1\ninc: file:c.yaml\n", "c.yaml": "x: 1\n"}
    expected = "a:\n  b: 1\n  c: 2\ninc: file:c.yaml\n"
    assert_set(theatre, files, "a.c", "2", {"troupe.yml": expected})


def test_new_key_into_a_flow_mapping_form_include(theatre: Theatre) -> None:
    files = {"troupe.yml": "coder: {$ref: file:c.yaml, model: x}\n", "c.yaml": "a: 1\n"}
    expected = "coder: {$ref: file:c.yaml, model: x, t: 1}\n"
    assert_set(theatre, files, "coder.t", "1", {"troupe.yml": expected})


def test_flow_list_item_include_converted_in_place(theatre: Theatre) -> None:
    files = {"troupe.yml": "l: [file:a.yaml]\n", "a.yaml": "m: 1\n"}
    assert_set(theatre, files, "l.0.t", "1", {"troupe.yml": "l: [{$ref: file:a.yaml, t: 1}]\n"})


def test_new_multi_line_override_is_a_literal_block(theatre: Theatre) -> None:
    files = {"troupe.yml": "c: file:c.yaml\n", "c.yaml": "a: 1\n"}
    expected = "c:\n  $ref: file:c.yaml\n  p: |\n    l1\n    l2\n"
    assert_set(theatre, files, "c.p", '"l1\\nl2\\n"', {"troupe.yml": expected})
