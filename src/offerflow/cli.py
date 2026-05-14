from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import typer

from offerflow.config import ensure_default_config, load_config, load_env_file
from offerflow.crawl import run_crawl
from offerflow.extract import run_extract
from offerflow.errors import ErrorCode, OfferFlowError
from offerflow.output import dumps, error_envelope, success_envelope
from offerflow.paths import db_path
from offerflow.storage import apply_migrations, list_jobs as storage_list_jobs
from offerflow.storage import list_sources as storage_list_sources
from offerflow.storage import seed_registry, show_job as storage_show_job
from offerflow.timeutils import parse_since

app = typer.Typer(add_completion=False, no_args_is_help=True)
sources_app = typer.Typer(add_completion=False, no_args_is_help=True)
jobs_app = typer.Typer(add_completion=False, no_args_is_help=True)
crawl_app = typer.Typer(add_completion=False, no_args_is_help=True)
extract_app = typer.Typer(add_completion=False, no_args_is_help=True)
app.add_typer(sources_app, name="sources")
app.add_typer(jobs_app, name="jobs")
app.add_typer(crawl_app, name="crawl")
app.add_typer(extract_app, name="extract")


def emit(payload: dict[str, Any]) -> None:
    typer.echo(dumps(payload))


def run_json(command: str, fn: Any) -> None:
    try:
        data = fn()
    except OfferFlowError as exc:
        emit(error_envelope(command, exc))
        raise typer.Exit(exc.exit_code) from exc
    except Exception as exc:
        error = OfferFlowError(
            ErrorCode.INVALID_ARGUMENT,
            "Unexpected command failure.",
            {"error": str(exc)},
            exit_code=1,
        )
        emit(error_envelope(command, error))
        raise typer.Exit(1) from exc
    emit(success_envelope(command, data))


@app.command("init")
def init() -> None:
    def action() -> dict[str, Any]:
        config_file, config_created = ensure_default_config()
        load_env_file()
        migrations = apply_migrations()
        seed_registry()
        return {
            "config_path": str(config_file),
            "config_created": config_created,
            "db_path": str(db_path()),
            "migrations_applied": migrations,
        }

    run_json("init", action)


@app.command("doctor")
def doctor() -> None:
    def action() -> dict[str, Any]:
        config = load_config(required=False)
        load_env_file()
        default_profile = (config.get("llm_profiles") or {}).get("default") or {}
        api_key_env = default_profile.get("api_key_env")
        return {
            "config_found": Path("config.yaml").exists(),
            "db_initialized": db_path().exists(),
            "db_path": str(db_path()),
            "llm_default_model": default_profile.get("model"),
            "api_key_env": api_key_env,
            "api_key_env_present": bool(api_key_env and os.getenv(api_key_env)),
        }

    run_json("doctor", action)


@sources_app.command("list")
def sources_list() -> None:
    def action() -> dict[str, Any]:
        return {"sources": storage_list_sources()}

    run_json("sources list", action)


@crawl_app.command("run")
def crawl_run(
    all_sources: bool = typer.Option(False, "--all"),
    company: str | None = typer.Option(None, "--company"),
    source: str | None = typer.Option(None, "--source"),
    channel: str | None = typer.Option(None, "--channel"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    limit: int | None = typer.Option(None, "--limit", min=1, max=500),
) -> None:
    def action() -> dict[str, Any]:
        result = run_crawl(
            all_sources=all_sources,
            company=company,
            source=source,
            channel=channel,
            dry_run=dry_run,
            limit=limit,
        )
        if result["partial_failure"]:
            raise OfferFlowError(
                ErrorCode.FETCH_FAILED,
                "One or more sources failed during crawl.",
                result,
                exit_code=2,
            )
        return result

    run_json("crawl run", action)


@extract_app.command("run")
def extract_run(
    pending: bool = typer.Option(False, "--pending"),
    failed: bool = typer.Option(False, "--failed"),
    limit: int = typer.Option(50, "--limit", min=1, max=500),
) -> None:
    def action() -> dict[str, Any]:
        result = run_extract(pending=pending, failed=failed, limit=limit)
        if result["failed"]:
            raise OfferFlowError(
                ErrorCode.EXTRACT_FAILED,
                "One or more extraction jobs failed.",
                result,
                exit_code=2,
            )
        return result

    run_json("extract run", action)


@jobs_app.command("list")
def jobs_list(
    company: str | None = typer.Option(None, "--company"),
    source: str | None = typer.Option(None, "--source"),
    channel: str | None = typer.Option(None, "--channel"),
    status: str | None = typer.Option(None, "--status"),
    new: bool = typer.Option(False, "--new"),
    changed: bool = typer.Option(False, "--changed"),
    closed: bool = typer.Option(False, "--closed"),
    since: str | None = typer.Option(None, "--since"),
    limit: int = typer.Option(50, "--limit", min=1, max=500),
) -> None:
    def action() -> dict[str, Any]:
        since_value = parse_since(since)
        since_filters = sum(1 for enabled in (new, changed, closed) if enabled)
        if since and since_filters == 0:
            raise OfferFlowError(
                ErrorCode.INVALID_ARGUMENT,
                "--since must be paired with --new, --changed, or --closed for jobs list.",
                {"since": since},
                exit_code=1,
            )
        if since_filters > 1:
            raise OfferFlowError(
                ErrorCode.INVALID_ARGUMENT,
                "Use only one of --new, --changed, or --closed with jobs list.",
                {"new": new, "changed": changed, "closed": closed},
                exit_code=1,
            )
        jobs = storage_list_jobs(
            company=company,
            source=source,
            channel=channel,
            status=status,
            new_since=since_value if new else None,
            changed_since=since_value if changed else None,
            closed_since=since_value if closed else None,
            limit=limit,
        )
        return {"jobs": jobs, "count": len(jobs)}

    run_json("jobs list", action)


@jobs_app.command("show")
def jobs_show(
    job_id: str,
    with_extraction: bool = typer.Option(False, "--with-extraction"),
) -> None:
    def action() -> dict[str, Any]:
        return {"job": storage_show_job(None, job_id, with_extraction=with_extraction)}

    run_json("jobs show", action)
