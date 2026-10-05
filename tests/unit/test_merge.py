"""Mapping-form includes load merged (spec FR-400 to FR-405, D-46; research O-1, O-2)."""

from pathlib import Path

from troupe.config.commands import resolve
from troupe.config.leaves import to_value
from troupe.config.loader import Loaded, load
from troupe.config.paths import ConfigPath
from troupe.config.tree import Located, LocatedMapping, LocatedScalar, shared_part

CODER = "a: 1\nb: 2\nlimits: {retries: 2, timeout: 10}\ntools: [git, shell]\n"


def write(root: Path, relpath: str, content: str) -> None:
    path = root / ".troupe" / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def loaded_with(root: Path, overrides: str, coder: str = CODER) -> Loaded:
    write(root, "c.yaml", coder)
    write(root, "troupe.yml", "coder:\n  $ref: file:c.yaml\n" + overrides)
    return load(root)


def at(loaded: Loaded, path: str) -> Located:
    return resolve(loaded.root, ConfigPath.parse(path))


def file_of(loaded: Loaded, path: str) -> str:
    node = at(loaded, path)
    assert isinstance(node, LocatedScalar)
    return node.file.path.name


def keys(node: Located) -> list[str]:
    assert isinstance(node, LocatedMapping)
    return [str(key.value) for key, _ in node.entries]


def test_override_scalar_replaces_and_keeps_the_included_position(tmp_path: Path) -> None:
    loaded = loaded_with(tmp_path, "  a: 9\n")
    assert keys(at(loaded, "coder")) == ["a", "b", "limits", "tools"]
    assert to_value(at(loaded, "coder.a")) == 9
    assert file_of(loaded, "coder.a") == "troupe.yml"
    assert file_of(loaded, "coder.b") == "c.yaml"


def test_override_only_keys_come_after_included_keys_in_written_order(tmp_path: Path) -> None:
    loaded = loaded_with(tmp_path, "  z: 1\n  y: 2\n")
    assert keys(at(loaded, "coder")) == ["a", "b", "limits", "tools", "z", "y"]


def test_mappings_merge_recursively(tmp_path: Path) -> None:
    loaded = loaded_with(tmp_path, "  limits:\n    timeout: 30\n")
    assert to_value(at(loaded, "coder.limits")) == {"retries": 2, "timeout": 30}
    assert file_of(loaded, "coder.limits.retries") == "c.yaml"
    assert file_of(loaded, "coder.limits.timeout") == "troupe.yml"


def test_override_list_replaces_included_list(tmp_path: Path) -> None:
    loaded = loaded_with(tmp_path, "  tools: [lint]\n")
    assert to_value(at(loaded, "coder.tools")) == ["lint"]
    assert to_value(at(loaded, "coder.b")) == 2  # merged, not just read from the main file


def test_override_mapping_replaces_included_scalar(tmp_path: Path) -> None:
    loaded = loaded_with(tmp_path, "  a: {x: 1}\n")
    assert to_value(at(loaded, "coder.a")) == {"x": 1}
    assert to_value(at(loaded, "coder.b")) == 2  # merged, not just read from the main file


def test_override_scalar_replaces_included_mapping(tmp_path: Path) -> None:
    loaded = loaded_with(tmp_path, "  limits: none\n")
    assert to_value(at(loaded, "coder.limits")) == "none"
    assert to_value(at(loaded, "coder.b")) == 2  # merged, not just read from the main file


def test_ref_only_mapping_equals_scalar_form(tmp_path: Path) -> None:
    write(tmp_path, "c.yaml", CODER)
    write(tmp_path, "p.md", "Be terse.\n")
    write(
        tmp_path,
        "troupe.yml",
        "a: {$ref: file:c.yaml}\nb: file:c.yaml\np: {$ref: file:p.md}\nq: file:p.md\n",
    )
    loaded = load(tmp_path)
    assert to_value(at(loaded, "a")) == to_value(at(loaded, "b"))
    assert to_value(at(loaded, "p")) == to_value(at(loaded, "q")) == "Be terse.\n"


def test_ref_is_not_an_entry(tmp_path: Path) -> None:
    loaded = loaded_with(tmp_path, "  limits:\n    timeout: 30\n")
    assert "$ref" not in keys(at(loaded, "coder"))
    assert "$ref" not in keys(at(loaded, "coder.limits"))


def test_merged_nodes_remember_site_and_overrides(tmp_path: Path) -> None:
    loaded = loaded_with(tmp_path, "  limits:\n    timeout: 30\n")
    root = at(loaded, "coder")
    assert isinstance(root, LocatedMapping)
    assert root.included_by is not None and root.included_by.value == "file:c.yaml"
    site = root.include_site
    assert site is not None and site.file.path.name == "troupe.yml"
    assert keys(site) == ["$ref", "limits"]
    assert root.overrides is site
    limits = at(loaded, "coder.limits")
    assert isinstance(limits, LocatedMapping)
    assert limits.overrides is site.get("limits")


def test_merged_mapping_keeps_its_base(tmp_path: Path) -> None:
    """Step 5 CR-B research I-2: the base holds only the included file's entries, in order."""
    loaded = loaded_with(tmp_path, "  z: 1\n  a: 9\n")
    root = at(loaded, "coder")
    assert isinstance(root, LocatedMapping) and root.base is not None
    assert keys(root.base) == ["a", "b", "limits", "tools"]
    assert {key.file.path.name for key, _ in root.base.entries} == {"c.yaml"}


def test_shared_part_follows_nested_bases(tmp_path: Path) -> None:
    """Step 5 CR-B: nested includes give the deepest file's mapping."""
    write(tmp_path, "m.yaml", "a: 1\n")
    write(tmp_path, "coder.yaml", "model: {$ref: file:m.yaml, b: 2}\n")
    write(tmp_path, "troupe.yml", "coder:\n  $ref: file:coder.yaml\n  model:\n    c: 3\n")
    model = at(load(tmp_path), "coder.model")
    assert isinstance(model, LocatedMapping)
    shared = shared_part(model)
    assert shared.file.path.name == "m.yaml"
    assert keys(shared) == ["a"]
