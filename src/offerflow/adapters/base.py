from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JobRef:
    company_id: str
    company_name: str
    source_id: str
    source_job_id: str | None
    detail_url: str
    title: str | None = None
    location: str | None = None
    business_unit: str | None = None
    channel: str = "unknown"
    posted_at: str | None = None


@dataclass(frozen=True)
class FetchedJob:
    ref: JobRef
    raw_payload: str
    raw_payload_type: str


class SourceAdapter:
    company_id: str
    company_name: str
    source_id: str
    source_name: str

    def search(self, *, channel: str | None = None, limit: int | None = None) -> list[JobRef]:
        raise NotImplementedError

    def fetch(self, ref: JobRef) -> FetchedJob:
        raise NotImplementedError
