from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any

from offerflow.config import load_config, load_env_file
from offerflow.errors import ErrorCode, OfferFlowError
from offerflow.storage import latest_failed_attempt_count, list_pending_html_extractions, record_extraction


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self._skip = True
        if tag.lower() in {"p", "div", "br", "li", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self._skip = False

    def handle_data(self, data: str) -> None:
        if not self._skip:
            text = data.strip()
            if text:
                self.parts.append(text)

    def markdown(self) -> str:
        text = " ".join(self.parts)
        text = re.sub(r"\s*\n\s*", "\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n\n".join(lines)


def run_extract(*, pending: bool = False, failed: bool = False, limit: int = 50) -> dict[str, Any]:
    if not pending and not failed:
        raise OfferFlowError(
            ErrorCode.INVALID_ARGUMENT,
            "Specify --pending or --failed for extract run.",
            {},
            exit_code=1,
        )
    if pending and failed:
        raise OfferFlowError(
            ErrorCode.INVALID_ARGUMENT,
            "Use only one of --pending or --failed for extract run.",
            {},
            exit_code=1,
        )

    load_env_file()
    config = load_config(required=True)
    extractor_config = config.get("extractor") or {}
    extractor = extractor_config.get("provider") or "mineru-html"
    llm_profile = extractor_config.get("llm_profile") or "default"
    profile = (config.get("llm_profiles") or {}).get(llm_profile) or {}
    model = profile.get("model")

    if extractor != "mineru-html":
        raise OfferFlowError(
            ErrorCode.EXTRACT_FAILED,
            "Only mineru-html extractor is supported in the MVP.",
            {"extractor": extractor},
            exit_code=1,
        )

    items = list_pending_html_extractions(
        extractor=extractor,
        llm_profile=llm_profile,
        include_failed=failed,
        limit=limit,
    )
    results = []
    for item in items:
        attempt_count = latest_failed_attempt_count(
            snapshot_id=item["snapshot_id"],
            extractor=extractor,
            llm_profile=llm_profile,
        ) + 1
        try:
            markdown = extract_html_to_markdown(item["raw_payload"])
            extraction_id = record_extraction(
                job_id=item["job_id"],
                snapshot_id=item["snapshot_id"],
                extractor=extractor,
                extractor_version="builtin-html-text-0.1",
                llm_profile=llm_profile,
                model=model,
                status="succeeded",
                output_markdown=markdown,
                attempt_count=attempt_count,
            )
            results.append({"job_id": item["job_id"], "snapshot_id": item["snapshot_id"], "status": "succeeded", "extraction_id": extraction_id})
        except Exception as exc:
            extraction_id = record_extraction(
                job_id=item["job_id"],
                snapshot_id=item["snapshot_id"],
                extractor=extractor,
                extractor_version="builtin-html-text-0.1",
                llm_profile=llm_profile,
                model=model,
                status="failed",
                error_code=ErrorCode.EXTRACT_FAILED,
                error_message=str(exc),
                attempt_count=attempt_count,
            )
            results.append({"job_id": item["job_id"], "snapshot_id": item["snapshot_id"], "status": "failed", "extraction_id": extraction_id})
    failures = sum(1 for item in results if item["status"] == "failed")
    return {"extractor": extractor, "llm_profile": llm_profile, "model": model, "processed": len(results), "failed": failures, "results": results}


def extract_html_to_markdown(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    markdown = parser.markdown()
    if not markdown:
        raise OfferFlowError(ErrorCode.EXTRACT_FAILED, "HTML extraction produced empty markdown.", {}, exit_code=2)
    return markdown
