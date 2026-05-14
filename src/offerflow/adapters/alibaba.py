from __future__ import annotations

import json
from typing import Any

from offerflow.adapters.base import FetchedJob, JobRef, SourceAdapter
from offerflow.http import HttpSession


class AlibabaAdapter(SourceAdapter):
    company_id = "alibaba"
    company_name = "阿里巴巴"
    source_id = "alibaba-main"
    source_name = "阿里巴巴招聘官网"

    landing_url = "https://talent-holding.alibaba.com/off-campus/position-list?lang=zh"
    search_url = "https://talent-holding.alibaba.com/position/search"

    def __init__(self) -> None:
        self.session = HttpSession()
        self._csrf = ""
        self._cache: dict[str, dict[str, Any]] = {}

    def search(self, *, channel: str | None = None, limit: int | None = None) -> list[JobRef]:
        self._prime_session()
        page_size = min(max(limit or 20, 1), 50)
        payload = {
            "channel": "group_official_site",
            "language": "zh",
            "batchId": "",
            "categories": "",
            "deptCodes": [],
            "key": "",
            "pageIndex": 1,
            "pageSize": page_size,
            "regions": "",
            "subCategories": "",
            "shareType": "",
            "shareId": "",
            "myReferralShareCode": "",
        }
        data = self.session.post_json(f"{self.search_url}?_csrf={self._csrf}", payload, headers=self._headers())
        posts = ((data.get("content") or {}).get("datas") or []) if data.get("success") else []
        refs = []
        for post in posts:
            ref = self._to_ref(post, channel=channel)
            self._cache[ref.source_job_id or ref.detail_url] = post
            refs.append(ref)
        return refs[:limit] if limit else refs

    def fetch(self, ref: JobRef) -> FetchedJob:
        payload = self._cache.get(ref.source_job_id or ref.detail_url) or {"ref": ref.__dict__}
        return FetchedJob(ref=ref, raw_payload=json.dumps(payload, ensure_ascii=False, sort_keys=True), raw_payload_type="json")

    def _prime_session(self) -> None:
        self.session.get_text(self.landing_url, headers=self._headers())
        for cookie in self.session.cookie_jar:
            if cookie.name == "XSRF-TOKEN":
                self._csrf = cookie.value
                return

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json, text/plain, */*",
            "Referer": self.landing_url,
            "Origin": "https://talent-holding.alibaba.com",
            "bx-v": "2.5.11",
        }

    def _to_ref(self, post: dict[str, Any], *, channel: str | None) -> JobRef:
        source_job_id = str(post.get("id") or post.get("code") or "")
        locations = post.get("workLocations") or []
        categories = post.get("categories") or []
        return JobRef(
            company_id=self.company_id,
            company_name=self.company_name,
            source_id=self.source_id,
            source_job_id=source_job_id,
            detail_url=f"https://talent-holding.alibaba.com{post.get('positionUrl') or ''}",
            title=post.get("name"),
            location=",".join(locations),
            business_unit=",".join(categories) if isinstance(categories, list) else categories,
            channel=channel or "social",
            posted_at=str(post.get("publishTime")) if post.get("publishTime") else None,
        )
