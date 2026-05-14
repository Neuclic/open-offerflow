from __future__ import annotations

import pytest

from offerflow.errors import OfferFlowError
from offerflow.storage import (
    apply_migrations,
    list_jobs,
    mark_missing_for_source,
    normalize_url,
    seed_registry,
    show_job,
    stable_job_id,
    upsert_job_snapshot,
)
from offerflow.timeutils import parse_since


def test_stable_job_id_prefers_source_job_id():
    assert stable_job_id("tencent", "123", "https://example.com/a") == stable_job_id(
        "tencent", "123", "https://example.com/b"
    )


def test_stable_job_id_falls_back_to_normalized_url():
    assert stable_job_id("tencent", detail_url="HTTPS://EXAMPLE.com/jobs?a=1&b=2#frag") == stable_job_id(
        "tencent", detail_url="https://example.com/jobs?b=2&a=1"
    )


def test_normalize_url_sorts_query_and_removes_fragment():
    assert normalize_url("HTTPS://Example.COM/jobs/?b=2&a=1#top") == "https://example.com/jobs?a=1&b=2"


def test_parse_since_rejects_naive_iso_timestamp():
    with pytest.raises(OfferFlowError):
        parse_since("2026-05-14T00:00:00")


def test_upsert_job_snapshot_and_show_job(tmp_path):
    apply_migrations(tmp_path)
    seed_registry(tmp_path)

    result = upsert_job_snapshot(
        tmp_path,
        company_id="tencent",
        company_name="腾讯",
        source_id="tencent-main",
        source_job_id="abc",
        title="Backend Engineer",
        location="Shenzhen",
        channel="campus",
        detail_url="https://careers.tencent.com/job/abc",
        raw_payload='{"id":"abc","title":"Backend Engineer"}',
        raw_payload_type="json",
    )

    assert result["status"] == "new"
    assert result["snapshot_created"] is True

    job = show_job(tmp_path, result["job_id"])
    assert job["title"] == "Backend Engineer"
    assert job["current_snapshot"]["raw_payload_type"] == "json"

    jobs = list_jobs(tmp_path, source="tencent-main", new_since="2000-01-01T00:00:00Z")
    assert [item["job_id"] for item in jobs] == [result["job_id"]]


def test_mark_missing_for_source_closes_after_two_misses(tmp_path):
    apply_migrations(tmp_path)
    seed_registry(tmp_path)
    result = upsert_job_snapshot(
        tmp_path,
        company_id="tencent",
        company_name="腾讯",
        source_id="tencent-main",
        source_job_id="abc",
        title="Backend Engineer",
        detail_url="https://careers.tencent.com/job/abc",
        raw_payload='{"id":"abc"}',
        raw_payload_type="json",
    )

    first = mark_missing_for_source(tmp_path, source_id="tencent-main", seen_job_ids=set())
    assert first == {"updated": 1, "closed": 0}
    assert show_job(tmp_path, result["job_id"])["status"] == "changed"

    second = mark_missing_for_source(tmp_path, source_id="tencent-main", seen_job_ids=set())
    assert second == {"updated": 1, "closed": 1}
    closed_job = show_job(tmp_path, result["job_id"])
    assert closed_job["status"] == "closed"
    assert closed_job["missing_count"] == 2
