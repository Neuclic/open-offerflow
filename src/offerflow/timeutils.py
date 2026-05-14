from __future__ import annotations

from datetime import UTC, datetime, timedelta

from offerflow.errors import ErrorCode, OfferFlowError


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_since(value: str | None) -> str | None:
    if not value:
        return None

    raw = value.strip()
    now = datetime.now(UTC).replace(microsecond=0)
    if raw.endswith("h") and raw[:-1].isdigit():
        return (now - timedelta(hours=int(raw[:-1]))).isoformat().replace("+00:00", "Z")
    if raw.endswith("d") and raw[:-1].isdigit():
        return (now - timedelta(days=int(raw[:-1]))).isoformat().replace("+00:00", "Z")

    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OfferFlowError(
            ErrorCode.INVALID_ARGUMENT,
            "--since must be a duration like 24h/7d or an ISO 8601 timestamp.",
            {"since": value},
            exit_code=1,
        ) from exc

    if parsed.tzinfo is None:
        raise OfferFlowError(
            ErrorCode.INVALID_ARGUMENT,
            "--since ISO 8601 values must include a timezone.",
            {"since": value},
            exit_code=1,
        )
    return parsed.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
