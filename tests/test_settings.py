from pathlib import Path

from solr_metal.settings import load_settings


def test_load_settings_respects_precedence(tmp_path: Path, monkeypatch) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        "[tool.solr-metal]\noutput_root = 'from-config'\nversion_check_enabled = false\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SM_OUTPUT_ROOT", "from-env")
    loaded = load_settings(config_path=config, cli_overrides={"output_root": Path("from-cli")})
    assert loaded.settings.output_root == Path("from-cli")


def test_load_settings_tracks_loaded_files(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text("[tool.solr-metal]\noutput_root = 'runs'\n", encoding="utf-8")
    loaded = load_settings(config_path=config)
    assert config in loaded.config_files
