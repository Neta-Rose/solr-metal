from solr_metal.versioning import StaticJsonVersionSource


def test_static_json_version_source(monkeypatch) -> None:
    monkeypatch.setattr(
        "solr_metal.versioning._fetch_json",
        lambda url, timeout: {"version": "9.9.9"},
    )
    monkeypatch.setattr(
        "solr_metal.versioning.current_version",
        lambda package_name="solr-metal": "0.1.0",
    )
    status = StaticJsonVersionSource("https://versions.example/api/solr-metal.json").fetch_latest(
        "solr-metal",
        2.5,
    )
    assert status.latest == "9.9.9"
    assert status.update_available is True
