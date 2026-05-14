from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Company:
    company_id: str
    company_name: str


@dataclass(frozen=True)
class Source:
    source_id: str
    source_name: str
    company_id: str
    adapter: str


COMPANIES: tuple[Company, ...] = (
    Company("tencent", "腾讯"),
    Company("bytedance", "字节跳动"),
    Company("alibaba", "阿里巴巴"),
)

SOURCES: tuple[Source, ...] = (
    Source("tencent-main", "腾讯招聘官网", "tencent", "tencent"),
    Source("bytedance-main", "字节跳动招聘官网", "bytedance", "bytedance"),
    Source("alibaba-main", "阿里巴巴招聘官网", "alibaba", "alibaba"),
)
