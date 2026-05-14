from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from offerflow.errors import ErrorCode, OfferFlowError
from offerflow.paths import db_path, logs_dir, migrations_dir, runtime_dir
from offerflow.registry import COMPANIES, SOURCES
from offerflow.timeutils import utc_now


def stable_job_id(company_id: str, source_job_id: str | None = None, detail_url: str | None = None) -> str:
    if source_job_id:
        key = f"{company_id}:{source_job_id.strip()}"
    elif detail_url:
        key = f"{company_id}:{normalize_url(detail_url)}"
    else:
        raise OfferFlowError(
            ErrorCode.INVALID_ARGUMENT,
            "stable_job_id requires source_job_id or detail_url.",
            {"company_id": company_id},
            exit_code=1,
        )
    return f"job_{hashlib.sha256(key.encode('utf-8')).hexdigest()[:16]}"


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/") or "/"
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
    return urlunsplit((scheme, netloc, path, query, ""))


def payload_hash(raw_payload: str) -> str:
    return hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()


def content_hash(fields: dict[str, Any]) -> str:
    body = json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def ensure_runtime_dirs(base_dir: Path | None = None) -> None:
    runtime_dir(base_dir).mkdir(parents=True, exist_ok=True)
    logs_dir(base_dir).mkdir(parents=True, exist_ok=True)


def connect(base_dir: Path | None = None, *, require_initialized: bool = True) -> sqlite3.Connection:
    path = db_path(base_dir)
    if require_initialized and not path.exists():
        raise OfferFlowError(
            ErrorCode.DB_NOT_INITIALIZED,
            "Local database is not initialized.",
            {"db_path": str(path)},
            exit_code=1,
        )
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def apply_migrations(base_dir: Path | None = None) -> list[str]:
    ensure_runtime_dirs(base_dir)
    conn = connect(base_dir, require_initialized=False)
    applied_now: list[str] = []
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        applied = {row["version"] for row in conn.execute("SELECT version FROM schema_migrations")}
        for path in sorted(migrations_dir().glob("*.sql")):
            version = path.stem
            if version in applied:
                continue
            try:
                conn.executescript(path.read_text(encoding="utf-8"))
                conn.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (version, utc_now()),
                )
                applied_now.append(version)
            except sqlite3.DatabaseError as exc:
                conn.rollback()
                raise OfferFlowError(
                    ErrorCode.MIGRATION_FAILED,
                    "Failed to apply database migration.",
                    {"migration": path.name, "error": str(exc)},
                    exit_code=3,
                ) from exc
        conn.commit()
    finally:
        conn.close()
    return applied_now


def seed_registry(base_dir: Path | None = None) -> None:
    conn = connect(base_dir)
    try:
        for company in COMPANIES:
            conn.execute(
                """
                INSERT INTO companies(company_id, company_name, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(company_id) DO UPDATE SET
                    company_name = excluded.company_name,
                    updated_at = excluded.updated_at
                """,
                (company.company_id, company.company_name, utc_now(), utc_now()),
            )
        for source in SOURCES:
            conn.execute(
                """
                INSERT INTO sources(source_id, source_name, company_id, adapter, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    source_name = excluded.source_name,
                    company_id = excluded.company_id,
                    adapter = excluded.adapter,
                    is_active = excluded.is_active,
                    updated_at = excluded.updated_at
                """,
                (source.source_id, source.source_name, source.company_id, source.adapter, utc_now(), utc_now()),
            )
        conn.commit()
    finally:
        conn.close()


def list_sources(base_dir: Path | None = None) -> list[dict[str, Any]]:
    conn = connect(base_dir)
    try:
        rows = conn.execute(
            """
            SELECT s.source_id, s.source_name, s.company_id, c.company_name, s.adapter, s.is_active
            FROM sources s
            JOIN companies c ON c.company_id = s.company_id
            ORDER BY s.company_id, s.source_id
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def start_crawl_run(
    base_dir: Path | None = None,
    *,
    crawl_run_id: str,
    source_id: str | None = None,
    company_id: str | None = None,
    channel: str | None = None,
) -> None:
    conn = connect(base_dir)
    try:
        conn.execute(
            """
            INSERT INTO crawl_runs(crawl_run_id, source_id, company_id, channel, status, started_at)
            VALUES (?, ?, ?, ?, 'running', ?)
            """,
            (crawl_run_id, source_id, company_id, channel, utc_now()),
        )
        conn.commit()
    finally:
        conn.close()


def finish_crawl_run(
    base_dir: Path | None = None,
    *,
    crawl_run_id: str,
    status: str,
    jobs_seen: int = 0,
    jobs_changed: int = 0,
    jobs_failed: int = 0,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    conn = connect(base_dir)
    try:
        conn.execute(
            """
            UPDATE crawl_runs
            SET status = ?, finished_at = ?, jobs_seen = ?, jobs_changed = ?,
                jobs_failed = ?, error_code = ?, error_message = ?
            WHERE crawl_run_id = ?
            """,
            (status, utc_now(), jobs_seen, jobs_changed, jobs_failed, error_code, error_message, crawl_run_id),
        )
        conn.commit()
    finally:
        conn.close()


def list_jobs(
    base_dir: Path | None = None,
    *,
    company: str | None = None,
    source: str | None = None,
    channel: str | None = None,
    status: str | None = None,
    new_since: str | None = None,
    changed_since: str | None = None,
    closed_since: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    for column, value in (
        ("company_id", company),
        ("source_id", source),
        ("channel", channel),
        ("status", status),
    ):
        if value:
            clauses.append(f"{column} = ?")
            params.append(value)
    if new_since:
        clauses.append("first_seen_at >= ?")
        params.append(new_since)
    if changed_since:
        clauses.append(
            """
            current_snapshot_id IN (
                SELECT snapshot_id
                FROM job_snapshots
                WHERE created_at >= ?
            )
            """
        )
        params.append(changed_since)
    if closed_since:
        clauses.append("closed_at >= ?")
        params.append(closed_since)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)

    conn = connect(base_dir)
    try:
        rows = conn.execute(
            f"""
            SELECT job_id, company_id, company_name, source_id, source_job_id, title,
                   location, business_unit, channel, detail_url, status, missing_count,
                   first_seen_at, last_seen_at, closed_at, current_snapshot_id, content_hash
            FROM jobs
            {where}
            ORDER BY last_seen_at DESC, first_seen_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def upsert_job_snapshot(
    base_dir: Path | None = None,
    *,
    company_id: str,
    company_name: str,
    source_id: str,
    detail_url: str,
    raw_payload: str,
    raw_payload_type: str,
    source_job_id: str | None = None,
    title: str | None = None,
    location: str | None = None,
    business_unit: str | None = None,
    channel: str | None = None,
    crawl_run_id: str | None = None,
) -> dict[str, Any]:
    if raw_payload_type not in {"json", "html"}:
        raise OfferFlowError(
            ErrorCode.UNSUPPORTED_PAYLOAD_TYPE,
            "raw_payload_type must be json or html.",
            {"raw_payload_type": raw_payload_type},
            exit_code=1,
        )

    now = utc_now()
    job_id = stable_job_id(company_id, source_job_id=source_job_id, detail_url=detail_url)
    raw_hash = payload_hash(raw_payload)
    c_hash = content_hash(
        {
            "company_id": company_id,
            "business_unit": business_unit,
            "title": title,
            "raw_payload_hash": raw_hash,
        }
    )

    conn = connect(base_dir)
    try:
        existing = conn.execute(
            "SELECT job_id, current_snapshot_id, content_hash, status FROM jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        snapshot_created = False
        status = "new"
        snapshot_id = existing["current_snapshot_id"] if existing else None

        snapshot_values: tuple[Any, ...] | None = None
        if not existing or existing["content_hash"] != c_hash:
            snapshot_id = f"snap_{hashlib.sha256(f'{job_id}:{raw_hash}:{now}'.encode('utf-8')).hexdigest()[:16]}"
            snapshot_values = (
                snapshot_id,
                job_id,
                crawl_run_id,
                raw_payload,
                raw_payload_type,
                raw_hash,
                c_hash,
                now,
            )
            snapshot_created = True
            status = "new" if not existing else "changed"
        else:
            status = existing["status"] if existing["status"] != "closed" else "changed"

        if existing:
            if snapshot_values:
                conn.execute(
                    """
                    INSERT INTO job_snapshots(
                        snapshot_id, job_id, crawl_run_id, raw_payload, raw_payload_type,
                        raw_payload_hash, content_hash, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    snapshot_values,
                )
            conn.execute(
                """
                UPDATE jobs
                SET company_name = ?, source_job_id = ?, title = ?, location = ?,
                    business_unit = ?, channel = ?, detail_url = ?, status = ?,
                    missing_count = 0, last_seen_at = ?, closed_at = NULL,
                    current_snapshot_id = ?, content_hash = ?
                WHERE job_id = ?
                """,
                (
                    company_name,
                    source_job_id,
                    title,
                    location,
                    business_unit,
                    channel or "unknown",
                    detail_url,
                    status,
                    now,
                    snapshot_id,
                    c_hash,
                    job_id,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO jobs(
                    job_id, company_id, company_name, source_id, source_job_id, title,
                    location, business_unit, channel, detail_url, status, missing_count,
                    first_seen_at, last_seen_at, closed_at, current_snapshot_id, content_hash
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, NULL, ?, ?)
                """,
                (
                    job_id,
                    company_id,
                    company_name,
                    source_id,
                    source_job_id,
                    title,
                    location,
                    business_unit,
                    channel or "unknown",
                    detail_url,
                    status,
                    now,
                    now,
                    snapshot_id,
                    c_hash,
                ),
            )
            if snapshot_values:
                conn.execute(
                    """
                    INSERT INTO job_snapshots(
                        snapshot_id, job_id, crawl_run_id, raw_payload, raw_payload_type,
                        raw_payload_hash, content_hash, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    snapshot_values,
                )
        conn.commit()
        return {
            "job_id": job_id,
            "snapshot_id": snapshot_id,
            "status": status,
            "snapshot_created": snapshot_created,
        }
    finally:
        conn.close()


def mark_missing_for_source(
    base_dir: Path | None = None,
    *,
    source_id: str,
    seen_job_ids: set[str],
    close_after: int = 2,
) -> dict[str, int]:
    now = utc_now()
    conn = connect(base_dir)
    try:
        rows = conn.execute(
            "SELECT job_id, missing_count FROM jobs WHERE source_id = ? AND status != 'closed'",
            (source_id,),
        ).fetchall()
        updated = 0
        closed = 0
        for row in rows:
            if row["job_id"] in seen_job_ids:
                continue
            next_missing = row["missing_count"] + 1
            next_status = "closed" if next_missing >= close_after else "changed"
            closed_at = now if next_status == "closed" else None
            conn.execute(
                """
                UPDATE jobs
                SET missing_count = ?, status = ?, closed_at = COALESCE(?, closed_at)
                WHERE job_id = ?
                """,
                (next_missing, next_status, closed_at, row["job_id"]),
            )
            updated += 1
            if next_status == "closed":
                closed += 1
        conn.commit()
        return {"updated": updated, "closed": closed}
    finally:
        conn.close()


def show_job(base_dir: Path | None, job_id: str, *, with_extraction: bool = False) -> dict[str, Any]:
    conn = connect(base_dir)
    try:
        job = conn.execute(
            """
            SELECT job_id, company_id, company_name, source_id, source_job_id, title,
                   location, business_unit, channel, detail_url, status, missing_count,
                   first_seen_at, last_seen_at, closed_at, current_snapshot_id, content_hash
            FROM jobs
            WHERE job_id = ?
            """,
            (job_id,),
        ).fetchone()
        if not job:
            raise OfferFlowError(
                ErrorCode.INVALID_ARGUMENT,
                "Job was not found.",
                {"job_id": job_id},
                exit_code=1,
            )
        result = dict(job)
        snapshot = conn.execute(
            """
            SELECT snapshot_id, raw_payload_type, raw_payload_hash, content_hash, created_at
            FROM job_snapshots
            WHERE snapshot_id = ?
            """,
            (result["current_snapshot_id"],),
        ).fetchone()
        result["current_snapshot"] = dict(snapshot) if snapshot else None

        if with_extraction and result["current_snapshot_id"]:
            extraction = conn.execute(
                """
                SELECT extraction_id, extractor, extractor_version, llm_profile, model,
                       status, output_markdown, error_code, error_message, attempt_count, created_at
                FROM job_extractions
                WHERE snapshot_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (result["current_snapshot_id"],),
            ).fetchone()
            result["latest_extraction"] = dict(extraction) if extraction else None
        return result
    finally:
        conn.close()


def list_pending_html_extractions(
    base_dir: Path | None = None,
    *,
    extractor: str,
    llm_profile: str,
    include_failed: bool = False,
    limit: int = 50,
) -> list[dict[str, Any]]:
    failed_clause = ""
    if include_failed:
        failed_clause = """
        OR EXISTS (
            SELECT 1
            FROM job_extractions failed
            WHERE failed.snapshot_id = js.snapshot_id
              AND failed.extractor = ?
              AND failed.llm_profile = ?
              AND failed.status = 'failed'
              AND failed.attempt_count < 2
        )
        """
    params: list[Any] = [extractor, llm_profile]
    if include_failed:
        params.extend([extractor, llm_profile])
    params.append(limit)

    conn = connect(base_dir)
    try:
        rows = conn.execute(
            f"""
            SELECT j.job_id, j.title, j.detail_url, js.snapshot_id, js.raw_payload, js.raw_payload_type
            FROM jobs j
            JOIN job_snapshots js ON js.snapshot_id = j.current_snapshot_id
            WHERE js.raw_payload_type = 'html'
              AND (
                NOT EXISTS (
                    SELECT 1
                    FROM job_extractions succeeded
                    WHERE succeeded.snapshot_id = js.snapshot_id
                      AND succeeded.extractor = ?
                      AND succeeded.llm_profile = ?
                      AND succeeded.status = 'succeeded'
                )
                {failed_clause}
              )
            ORDER BY js.created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def latest_failed_attempt_count(
    base_dir: Path | None = None,
    *,
    snapshot_id: str,
    extractor: str,
    llm_profile: str,
) -> int:
    conn = connect(base_dir)
    try:
        row = conn.execute(
            """
            SELECT attempt_count
            FROM job_extractions
            WHERE snapshot_id = ? AND extractor = ? AND llm_profile = ? AND status = 'failed'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (snapshot_id, extractor, llm_profile),
        ).fetchone()
        return int(row["attempt_count"]) if row else 0
    finally:
        conn.close()


def record_extraction(
    base_dir: Path | None = None,
    *,
    job_id: str,
    snapshot_id: str,
    extractor: str,
    extractor_version: str | None,
    llm_profile: str | None,
    model: str | None,
    status: str,
    output_markdown: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    attempt_count: int = 1,
) -> str:
    extraction_id = f"ext_{hashlib.sha256(f'{job_id}:{snapshot_id}:{extractor}:{utc_now()}'.encode('utf-8')).hexdigest()[:16]}"
    conn = connect(base_dir)
    try:
        conn.execute(
            """
            INSERT INTO job_extractions(
                extraction_id, job_id, snapshot_id, extractor, extractor_version,
                llm_profile, model, status, output_markdown, error_code,
                error_message, attempt_count, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                extraction_id,
                job_id,
                snapshot_id,
                extractor,
                extractor_version,
                llm_profile,
                model,
                status,
                output_markdown,
                error_code,
                error_message,
                attempt_count,
                utc_now(),
            ),
        )
        conn.commit()
        return extraction_id
    finally:
        conn.close()
