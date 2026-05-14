from __future__ import annotations

import json
import time
from typing import Any

from offerflow.adapters.base import FetchedJob, JobRef, SourceAdapter
from offerflow.http import add_query, get_json


CHANNEL_SOURCE_IDS = {
    "social": 1,
    "campus": 2,
    "internship": 2,
}


class TencentAdapter(SourceAdapter):
    company_id = "tencent"
    company_name = "腾讯"
    source_id = "tencent-main"
    source_name = "腾讯招聘官网"
    api_base = "https://careers.tencent.com/tencentcareer/api/post/Query"

    def search(self, *, channel: str | None = None, limit: int | None = None) -> list[JobRef]:
        page_size = min(max(limit or 50, 1), 100)
        params: dict[str, Any] = {
            "timestamp": int(time.time() * 1000),
            "countryId": "",
            "cityId": "",
            "bgIds": "",
            "productId": "",
            "categoryId": "",
            "parentCategoryId": "",
            "attrId": "",
            "keyword": "",
            "pageIndex": 1,
            "pageSize": page_size,
            "language": "zh-cn",
            "area": "cn",
        }
        if channel in CHANNEL_SOURCE_IDS:
            params["sourceId"] = CHANNEL_SOURCE_IDS[channel]
        data = get_json(add_query(self.api_base, params))
        posts = ((data.get("Data") or {}).get("Posts") or []) if data.get("Code") == 200 else []
        refs = [self._to_ref(post, channel=channel) for post in posts if post.get("PostId") or post.get("PostURL")]
        return refs[:limit] if limit else refs

    def fetch(self, ref: JobRef) -> FetchedJob:
        data = get_json(
            add_query(
                self.api_base,
                {
                    "timestamp": int(time.time() * 1000),
                    "keyword": ref.source_job_id or "",
                    "pageIndex": 1,
                    "pageSize": 1,
                    "language": "zh-cn",
                    "area": "cn",
                },
            )
        )
        posts = ((data.get("Data") or {}).get("Posts") or []) if data.get("Code") == 200 else []
        payload = posts[0] if posts else {"ref": ref.__dict__}
        return FetchedJob(ref=ref, raw_payload=json.dumps(payload, ensure_ascii=False, sort_keys=True), raw_payload_type="json")

    def _to_ref(self, post: dict[str, Any], *, channel: str | None) -> JobRef:
        source_job_id = str(post.get("PostId") or post.get("RecruitPostId") or "")
        detail_url = post.get("PostURL") or f"https://careers.tencent.com/jobdesc.html?postId={source_job_id}"
        return JobRef(
            company_id=self.company_id,
            company_name=self.company_name,
            source_id=self.source_id,
            source_job_id=source_job_id,
            detail_url=detail_url.replace("http://", "https://"),
            title=post.get("RecruitPostName"),
            location=post.get("LocationName"),
            business_unit=post.get("BGName") or post.get("ProductName"),
            channel=channel or self._channel_from_source(post.get("SourceID")),
            posted_at=post.get("LastUpdateTime"),
        )

    def _channel_from_source(self, source_id: Any) -> str:
        if source_id == 1:
            return "social"
        if source_id == 2:
            return "campus"
        return "unknown"
