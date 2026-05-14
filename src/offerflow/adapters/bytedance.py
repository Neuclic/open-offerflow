from __future__ import annotations

import json
from typing import Any

from offerflow.adapters.base import FetchedJob, JobRef, SourceAdapter
from offerflow.http import HttpSession


class ByteDanceAdapter(SourceAdapter):
    company_id = "bytedance"
    company_name = "字节跳动"
    source_id = "bytedance-main"
    source_name = "字节跳动招聘官网"

    landing_url = "https://jobs.bytedance.com/experienced/position"
    search_url = "https://jobs.bytedance.com/api/v1/search/job/posts"
    csrf_url = "https://jobs.bytedance.com/api/v1/csrf/token"
    signature = "dEk3aAAAAABX2mrlq0ilznRJN3AAB5O"

    def __init__(self) -> None:
        self.session = HttpSession()
        self._cache: dict[str, dict[str, Any]] = {}

    def search(self, *, channel: str | None = None, limit: int | None = None) -> list[JobRef]:
        self._prime_session()
        refs: list[JobRef] = []
        page_size = 10
        target = limit or 20
        for offset in range(0, target, page_size):
            payload = self._payload(limit=min(page_size, target - offset), offset=offset)
            data = self.session.post_json(f"{self.search_url}?{self._query(payload)}&_signature={self.signature}", payload, headers=self._headers())
            posts = ((data.get("data") or {}).get("job_post_list") or []) if data.get("code") == 0 else []
            for post in posts:
                ref = self._to_ref(post, channel=channel)
                self._cache[ref.source_job_id or ref.detail_url] = post
                refs.append(ref)
                if limit and len(refs) >= limit:
                    return refs
            if len(posts) < page_size:
                break
        return refs

    def fetch(self, ref: JobRef) -> FetchedJob:
        payload = self._cache.get(ref.source_job_id or ref.detail_url) or {"ref": ref.__dict__}
        return FetchedJob(ref=ref, raw_payload=json.dumps(payload, ensure_ascii=False, sort_keys=True), raw_payload_type="json")

    def _prime_session(self) -> None:
        self.session.get_text(self.landing_url, headers=self._headers())
        data = self.session.post_json(self.csrf_url, {}, headers=self._headers())
        token = (data.get("data") or {}).get("token")
        if token:
            self._csrf_token = token

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Referer": self.landing_url,
            "Origin": "https://jobs.bytedance.com",
            "website-path": "society",
            "portal-channel": "office",
            "portal-platform": "pc",
            "accept-language": "zh-CN",
        }
        token = getattr(self, "_csrf_token", None)
        if token:
            headers["x-csrf-token"] = token
        return headers

    def _payload(self, *, limit: int, offset: int) -> dict[str, Any]:
        return {
            "keyword": "",
            "limit": limit,
            "offset": offset,
            "job_category_id_list": [],
            "tag_id_list": [],
            "location_code_list": [],
            "subject_id_list": [],
            "recruitment_id_list": [],
            "portal_type": 2,
            "job_function_id_list": [],
            "storefront_id_list": [],
            "portal_entrance": 1,
        }

    def _query(self, payload: dict[str, Any]) -> str:
        parts = []
        for key, value in payload.items():
            if isinstance(value, list):
                value = ""
            parts.append(f"{key}={value}")
        return "&".join(parts)

    def _to_ref(self, post: dict[str, Any], *, channel: str | None) -> JobRef:
        source_job_id = str(post.get("id") or "")
        city = post.get("city_info") or {}
        category = post.get("job_category") or {}
        return JobRef(
            company_id=self.company_id,
            company_name=self.company_name,
            source_id=self.source_id,
            source_job_id=source_job_id,
            detail_url=f"https://jobs.bytedance.com/experienced/position/{source_job_id}/detail",
            title=post.get("title"),
            location=city.get("name") or ",".join(item.get("name", "") for item in post.get("city_list") or [] if item.get("name")),
            business_unit=category.get("name"),
            channel=channel or "social",
            posted_at=str(post.get("publish_time")) if post.get("publish_time") else None,
        )
