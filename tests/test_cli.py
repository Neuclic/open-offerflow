from __future__ import annotations

import json

from typer.testing import CliRunner

from offerflow.cli import app


runner = CliRunner()


def parse_json(stdout: str) -> dict:
    return json.loads(stdout)


def test_init_creates_config_database_and_sources(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0
    payload = parse_json(result.stdout)
    assert payload["ok"] is True
    assert (tmp_path / "config.yaml").exists()
    assert (tmp_path / ".offerflow" / "offerflow.sqlite").exists()
    assert payload["data"]["migrations_applied"] == ["0001_initial"]

    sources = runner.invoke(app, ["sources", "list"])
    source_payload = parse_json(sources.stdout)

    assert sources.exit_code == 0
    assert source_payload["ok"] is True
    assert [item["source_id"] for item in source_payload["data"]["sources"]] == [
        "alibaba-main",
        "bytedance-main",
        "tencent-main",
    ]


def test_sources_list_requires_initialized_database(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["sources", "list"])
    payload = parse_json(result.stdout)

    assert result.exit_code == 1
    assert payload["ok"] is False
    assert payload["error"]["code"] == "DB_NOT_INITIALIZED"


def test_jobs_list_is_empty_after_init(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])

    result = runner.invoke(app, ["jobs", "list", "--changed", "--since", "24h"])
    payload = parse_json(result.stdout)

    assert result.exit_code == 0
    assert payload["data"] == {"jobs": [], "count": 0}


def test_jobs_list_rejects_multiple_since_modes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])

    result = runner.invoke(app, ["jobs", "list", "--new", "--changed", "--since", "24h"])
    payload = parse_json(result.stdout)

    assert result.exit_code == 1
    assert payload["error"]["code"] == "INVALID_ARGUMENT"
