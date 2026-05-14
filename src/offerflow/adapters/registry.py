from __future__ import annotations

from offerflow.adapters.base import SourceAdapter
from offerflow.adapters.alibaba import AlibabaAdapter
from offerflow.adapters.bytedance import ByteDanceAdapter
from offerflow.adapters.tencent import TencentAdapter
from offerflow.errors import ErrorCode, OfferFlowError


ADAPTERS: dict[str, type[SourceAdapter]] = {
    "tencent": TencentAdapter,
    "bytedance": ByteDanceAdapter,
    "alibaba": AlibabaAdapter,
}


def get_adapter(adapter_name: str) -> SourceAdapter:
    adapter_class = ADAPTERS.get(adapter_name)
    if not adapter_class:
        raise OfferFlowError(
            ErrorCode.ADAPTER_NOT_FOUND,
            "Source adapter was not found.",
            {"adapter": adapter_name},
            exit_code=1,
        )
    return adapter_class()
