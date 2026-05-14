from __future__ import annotations

import json
from typing import Any

from offerflow import __version__
from offerflow.errors import OfferFlowError


def success_envelope(command: str, data: Any, warnings: list[str] | None = None) -> dict[str, Any]:
    return {
        "ok": True,
        "data": data,
        "warnings": warnings or [],
        "meta": {"command": command, "version": __version__},
    }


def error_envelope(command: str, error: OfferFlowError, warnings: list[str] | None = None) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": error.code,
            "message": error.message,
            "details": error.details,
        },
        "warnings": warnings or [],
        "meta": {"command": command, "version": __version__},
    }


def dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
