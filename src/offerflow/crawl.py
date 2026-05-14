from __future__ import annotations

import uuid
from dataclasses import asdict
from typing import Any

from offerflow.adapters import FetchedJob, JobRef, get_adapter
from offerflow.errors import ErrorCode, OfferFlowError
from offerflow.registry import SOURCES
from offerflow.storage import finish_crawl_run, mark_missing_for_source, stable_job_id, start_crawl_run, upsert_job_snapshot
from offerflow.timeutils import utc_now


def resolve_sources(*, all_sources: bool = False, company: str | None = None, source: str | None = None) -> list[dict[str, Any]]:
    selected = []
    for item in SOURCES:
        if source and item.source_id != source:
            continue
        if company and item.company_id != company:
            continue
        selected.append(item.__dict__)
    if source and not selected:
        raise OfferFlowError(ErrorCode.SOURCE_NOT_FOUND, "Source was not found.", {"source": source}, exit_code=1)
    if company and not selected:
        raise OfferFlowError(ErrorCode.SOURCE_NOT_FOUND, "Company has no configured sources.", {"company": company}, exit_code=1)
    if not (all_sources or company or source):
        raise OfferFlowError(
            ErrorCode.INVALID_ARGUMENT,
            "Specify --all, --company, or --source for crawl run.",
            {},
            exit_code=1,
        )
    return selected


def run_crawl(
    *,
    all_sources: bool = False,
    company: str | None = None,
    source: str | None = None,
    channel: str | None = None,
    dry_run: bool = False,
    limit: int | None = None,
) -> dict[str, Any]:
    source_configs = resolve_sources(all_sources=all_sources, company=company, source=source)
    crawl_run_id = f"crawl_{uuid.uuid4().hex[:16]}"
    results = []
    partial_failure = False
    for source_config in source_configs:
        source_run_id = f"{crawl_run_id}_{source_config['source_id'].replace('-', '_')}"
        try:
            if not dry_run:
                start_crawl_run(
                    crawl_run_id=source_run_id,
                    source_id=source_config["source_id"],
                    company_id=source_config["company_id"],
                    channel=channel,
                )
            adapter = get_adapter(source_config["adapter"])
            refs = adapter.search(channel=channel, limit=limit)
            if not refs:
                raise OfferFlowError(
                    ErrorCode.FETCH_FAILED,
                    "Adapter did not discover any job references.",
                    {"source_id": source_config["source_id"]},
                    exit_code=2,
                )
            samples = [asdict(ref) for ref in refs[:5]]
            stored = []
            fetch_success = 0
            if not dry_run:
                seen_job_ids: set[str] = set()
                for ref in refs:
                    fetched = adapter.fetch(ref)
                    fetch_success += 1
                    stored_item = store_fetched_job(fetched, crawl_run_id=source_run_id)
                    seen_job_ids.add(stored_item["job_id"])
                    stored.append(stored_item)
                missing = mark_missing_for_source(source_id=adapter.source_id, seen_job_ids=seen_job_ids)
                finish_crawl_run(
                    crawl_run_id=source_run_id,
                    status="succeeded",
                    jobs_seen=len(refs),
                    jobs_changed=sum(1 for item in stored if item.get("snapshot_created")),
                    jobs_failed=max(len(refs) - fetch_success, 0),
                )
            else:
                missing = {"updated": 0, "closed": 0}
            results.append(
                {
                    "source_id": source_config["source_id"],
                    "ok": True,
                    "job_refs": len(refs),
                    "details_fetched": fetch_success,
                    "stored": len(stored),
                    "missing": missing,
                    "samples": samples,
                }
            )
        except OfferFlowError as exc:
            partial_failure = True
            if not dry_run:
                try:
                    finish_crawl_run(
                        crawl_run_id=source_run_id,
                        status="failed",
                        error_code=exc.code,
                        error_message=exc.message,
                    )
                except OfferFlowError:
                    pass
            results.append(
                {
                    "source_id": source_config["source_id"],
                    "ok": False,
                    "error": {"code": exc.code, "message": exc.message, "details": exc.details},
                }
            )
    return {"crawl_run_id": crawl_run_id, "dry_run": dry_run, "results": results, "partial_failure": partial_failure}


def store_fetched_job(fetched: FetchedJob, *, crawl_run_id: str | None = None) -> dict[str, Any]:
    ref: JobRef = fetched.ref
    return upsert_job_snapshot(
        company_id=ref.company_id,
        company_name=ref.company_name,
        source_id=ref.source_id,
        source_job_id=ref.source_job_id,
        title=ref.title,
        location=ref.location,
        business_unit=ref.business_unit,
        channel=ref.channel,
        detail_url=ref.detail_url,
        raw_payload=fetched.raw_payload,
        raw_payload_type=fetched.raw_payload_type,
        crawl_run_id=crawl_run_id,
    )


def ref_job_id(ref: JobRef) -> str:
    return stable_job_id(ref.company_id, source_job_id=ref.source_job_id, detail_url=ref.detail_url)
