from pathlib import Path

from solr_metal.registry import Registry, load_file


def test_load_file_sets_source(tmp_path: Path) -> None:
    path = tmp_path / "test.yaml"
    path.write_text(
        "id: example.test\nname: Example\nkind: command\nspec:\n  command: ['echo', 'ok']\n",
        encoding="utf-8",
    )
    definition = load_file(path)
    assert definition.id == "example.test"
    assert definition.source == str(path)


def test_registry_loads_builtins_and_yaml(tmp_path: Path) -> None:
    (tmp_path / "custom.yaml").write_text(
        "id: custom.test\nname: Custom\nkind: command\nsuites: [smoke]\nspec:\n  command: ['echo', 'ok']\n",
        encoding="utf-8",
    )
    registry = Registry.load(tmp_path)
    assert registry.get("core.cluster.connected") is not None
    assert registry.get("openshift.version.readable") is not None
    assert registry.get("custom.test") is not None
