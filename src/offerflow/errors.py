from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ErrorCode:
    CONFIG_NOT_FOUND = "CONFIG_NOT_FOUND"
    DB_NOT_INITIALIZED = "DB_NOT_INITIALIZED"
    ADAPTER_NOT_FOUND = "ADAPTER_NOT_FOUND"
    SOURCE_NOT_FOUND = "SOURCE_NOT_FOUND"
    FETCH_FAILED = "FETCH_FAILED"
    EXTRACT_FAILED = "EXTRACT_FAILED"
    MIGRATION_FAILED = "MIGRATION_FAILED"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    UNSUPPORTED_PAYLOAD_TYPE = "UNSUPPORTED_PAYLOAD_TYPE"


@dataclass
class OfferFlowError(Exception):
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    exit_code: int = 1

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"
