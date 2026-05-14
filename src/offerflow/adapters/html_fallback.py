from __future__ import annotations

import hashlib
from html.parser import HTMLParser
from urllib.parse import urljoin

from offerflow.adapters.base import FetchedJob, JobRef, SourceAdapter
from offerflow.http import get_text


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            attr_map = dict(attrs)
            self._href = attr_map.get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href:
            text = " ".join(item for item in self._text if item).strip()
            self.links.append((self._href, text))
            self._href = None
            self._text = []


class HtmlFallbackAdapter(SourceAdapter):
    landing_url: str
    job_url_markers: tuple[str, ...] = ("position", "job")

    def search(self, *, channel: str | None = None, limit: int | None = None) -> list[JobRef]:
        html = get_text(self.landing_url)
        parser = _LinkParser()
        parser.feed(html)
        refs: list[JobRef] = []
        seen: set[str] = set()
        for href, text in parser.links:
            absolute = urljoin(self.landing_url, href)
            if absolute in seen:
                continue
            if not any(marker in absolute.lower() for marker in self.job_url_markers):
                continue
            seen.add(absolute)
            source_job_id = hashlib.sha256(absolute.encode("utf-8")).hexdigest()[:16]
            refs.append(
                JobRef(
                    company_id=self.company_id,
                    company_name=self.company_name,
                    source_id=self.source_id,
                    source_job_id=source_job_id,
                    detail_url=absolute,
                    title=text or None,
                    channel=channel or "unknown",
                )
            )
            if limit and len(refs) >= limit:
                break
        return refs

    def fetch(self, ref: JobRef) -> FetchedJob:
        return FetchedJob(ref=ref, raw_payload=get_text(ref.detail_url), raw_payload_type="html")


class ByteDanceAdapter(HtmlFallbackAdapter):
    company_id = "bytedance"
    company_name = "字节跳动"
    source_id = "bytedance-main"
    source_name = "字节跳动招聘官网"
    landing_url = "https://jobs.bytedance.com/experienced/position"


class AlibabaAdapter(HtmlFallbackAdapter):
    company_id = "alibaba"
    company_name = "阿里巴巴"
    source_id = "alibaba-main"
    source_name = "阿里巴巴招聘官网"
    landing_url = "https://talent.alibaba.com/off-campus/position-list"
