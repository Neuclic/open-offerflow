from __future__ import annotations

import json
from http.cookiejar import CookieJar
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

from offerflow.errors import ErrorCode, OfferFlowError


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; OpenOfferFlow/0.1; +https://github.com/Neuclic/open-offerflow)",
    "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
}


def get_text(url: str, *, headers: dict[str, str] | None = None, timeout: int = 20) -> str:
    req = Request(url, headers={**DEFAULT_HEADERS, **(headers or {})})
    try:
        with urlopen(req, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, "replace")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise OfferFlowError(
            ErrorCode.FETCH_FAILED,
            "Failed to fetch remote source.",
            {"url": url, "error": str(exc)},
            exit_code=2,
        ) from exc


class HttpSession:
    def __init__(self) -> None:
        self.cookie_jar = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookie_jar))

    def get_text(self, url: str, *, headers: dict[str, str] | None = None, timeout: int = 20) -> str:
        req = Request(url, headers={**DEFAULT_HEADERS, **(headers or {})})
        try:
            with self.opener.open(req, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, "replace")
        except (HTTPError, URLError, TimeoutError) as exc:
            raise OfferFlowError(
                ErrorCode.FETCH_FAILED,
                "Failed to fetch remote source.",
                {"url": url, "error": str(exc)},
                exit_code=2,
            ) from exc

    def get_json(self, url: str, *, headers: dict[str, str] | None = None, timeout: int = 20) -> dict[str, Any]:
        return _parse_json(self.get_text(url, headers=headers, timeout=timeout), url)

    def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        headers: dict[str, str] | None = None,
        timeout: int = 20,
    ) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        req = Request(
            url,
            data=body,
            headers={**DEFAULT_HEADERS, "Content-Type": "application/json", **(headers or {})},
            method="POST",
        )
        try:
            with self.opener.open(req, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return _parse_json(response.read().decode(charset, "replace"), url)
        except (HTTPError, URLError, TimeoutError) as exc:
            details: dict[str, Any] = {"url": url, "error": str(exc)}
            if isinstance(exc, HTTPError):
                details["body"] = exc.read().decode("utf-8", "replace")[:500]
            raise OfferFlowError(ErrorCode.FETCH_FAILED, "Failed to post JSON to remote source.", details, exit_code=2) from exc


def get_json(url: str, *, headers: dict[str, str] | None = None, timeout: int = 20) -> dict[str, Any]:
    text = get_text(url, headers=headers, timeout=timeout)
    return _parse_json(text, url)


def _parse_json(text: str, url: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise OfferFlowError(
            ErrorCode.FETCH_FAILED,
            "Remote source did not return JSON.",
            {"url": url, "sample": text[:200]},
            exit_code=2,
        ) from exc
    if not isinstance(data, dict):
        raise OfferFlowError(
            ErrorCode.FETCH_FAILED,
            "Remote JSON payload must be an object.",
            {"url": url},
            exit_code=2,
        )
    return data


def add_query(url: str, params: dict[str, Any]) -> str:
    return f"{url}?{urlencode(params)}"
