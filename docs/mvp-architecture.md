# Open OfferFlow MVP 开发架构

本文档固化 Open OfferFlow MVP 的开发规格。目标不是做一个传统前后端产品，而是先交付一个本地优先、命令行优先、适合编程智能体调用的岗位信息订阅工具。

## 1. 项目定位

Open OfferFlow 是面向求职者的岗位信息订阅工具，用于追踪公司官网招聘信息，并适配 Codex、Claude Code 等编程智能体。

MVP 聚焦三件事：

- 从公司官方招聘源发现岗位。
- 抓取岗位原始材料并落入本地 SQLite。
- 通过稳定 JSON CLI 让智能体查询、编排和后续处理。

MVP 不做简历匹配、不做自动投递、不做传统 Web Dashboard。

## 2. 技术栈

- Language: Python
- Package manager: uv
- Project metadata: pyproject.toml
- CLI framework: Typer
- Database: SQLite
- Migrations: SQL migration files
- Extractor integration: MinerU-HTML
- LLM provider: OpenAI-compatible API, defaulting to DeepSeek config

`pyproject.toml` 通过 console script 暴露命令：

```toml
[project.scripts]
offerflow = "offerflow.cli:app"
```

console script 的作用是让用户直接运行 `offerflow`，而不需要手写平台相关的 `.bat` 或 `.sh` 启动脚本。

## 3. MVP 范围

第一版只抓公司官方招聘官网，不接入 Boss 直聘、拉勾、LinkedIn、脉脉、牛客等第三方平台。

初始公司：

| company_id | company_name | source_id | source_name |
|---|---|---|---|
| tencent | 腾讯 | tencent-main | 腾讯招聘官网 |
| bytedance | 字节跳动 | bytedance-main | 字节跳动招聘官网 |
| alibaba | 阿里巴巴 | alibaba-main | 阿里巴巴招聘官网 |

后续可以增加更多 source。数据模型必须支持一个 company 下挂多个 source，例如网易和网易雷火可以分别建 source，但归属到同一个 company。

## 4. 核心概念

### Company

公司归属层，用于聚合多个招聘源。

```text
company_id: tencent
company_name: 腾讯
```

### Source

具体招聘源、招聘站点或事业部招聘入口。

```text
source_id: tencent-main
source_name: 腾讯招聘官网
company_id: tencent
adapter: tencent
```

### Channel

招聘类型，作为独立维度保存和筛选。

```text
campus
social
internship
unknown
```

CLI 支持指定 channel。不指定时默认抓全部 channel。

## 5. Adapter 架构

每个 source 由一个 adapter 负责。Adapter 内部可以拆成 searcher、fetcher 和 mapper。

```text
SourceAdapter
  Searcher: 发现岗位，返回轻量 JobRef
  Fetcher: 抓取岗位详情原始材料
  Mapper: 只做最小字段映射，不做语义解析
```

MVP 不做复杂 parser。岗位职责、要求、技能、薪资、匹配度等语义抽取交给后续 extractor / LLM 流程。

### JobRef 最低要求

`JobRef` 允许不完整，最低必须包含：

```text
company_id
source_id
detail_url
```

能拿到则补充：

```text
source_job_id
title
location
business_unit
channel
posted_at
```

## 6. Raw Payload 策略

Open OfferFlow 的事实层保存原始材料，不在 crawl 阶段做语义理解。

优先级：

1. API JSON
2. Static HTML

腾讯招聘这类 source 如果有干净公开 JSON 接口，直接保存 API JSON。没有 JSON 的 source 保存静态 HTML，然后交给 MinerU-HTML 做主内容抽取。

MVP 不保存：

```text
cleaned_html
rendered_html
rendered_text
raw_description_text
```

MVP 保存：

```text
raw_payload
raw_payload_type = json | html
raw_payload_hash
```

## 7. Extractor 架构

MinerU-HTML 是可选 extractor，但 MVP 要完成集成。`crawl` 和 `extract` 分开。

```bash
offerflow crawl run --all
offerflow extract run --pending
```

规则：

- `crawl` 不检查 LLM 或 MinerU-HTML 配置。
- `extract` 才检查 extractor 和 LLM 配置。
- MVP 只对 `raw_payload_type = html` 的最新 snapshot 运行 MinerU-HTML。
- API JSON source 暂时不跑 MinerU-HTML。
- MVP extraction 只保存 Markdown。
- JSON extraction 等自定义 schema 稳定后再加。

Pending 定义：

```text
latest job_snapshot exists
and no successful extraction for latest snapshot using current extractor config
```

失败要记录 extraction 任务，默认重试 1 次。

## 8. LLM 配置

项目使用统一 LLM profile。Extractor、后续 matcher、digest 都引用同一套配置。

`config.yaml` 提交到仓库，放非敏感配置：

```yaml
llm_profiles:
  default:
    provider: openai-compatible
    base_url: https://api.deepseek.com
    model: deepseek-v4-flash
    api_key_env: DEEPSEEK_API_KEY

extractor:
  provider: mineru-html
  llm_profile: default
```

敏感信息放 `.env`，不提交：

```env
DEEPSEEK_API_KEY=
```

## 9. 本地文件布局

项目配置放在仓库根目录：

```text
config.yaml
```

运行态数据放在 `.offerflow/`，并加入 `.gitignore`：

```text
.offerflow/
├─ offerflow.sqlite
└─ logs/
```

数据库迁移文件放在：

```text
migrations/
├─ 0001_initial.sql
└─ ...
```

## 10. 数据库设计

MVP 最小表：

```text
companies
sources
crawl_runs
jobs
job_snapshots
job_extractions
schema_migrations
```

### jobs

`jobs` 保存岗位当前状态。

关键字段：

```text
job_id
company_id
company_name
source_id
source_job_id
title
location
business_unit
channel
detail_url
status
missing_count
first_seen_at
last_seen_at
closed_at
current_snapshot_id
content_hash
```

`job_id` 使用稳定 hash：

```text
job_<hash>
```

生成逻辑：

```text
company_id + source_job_id
```

如果 source 没有稳定岗位 ID，则 fallback：

```text
company_id + normalized_detail_url
```

### job_snapshots

`job_snapshots` 保存岗位原始材料版本。新增岗位或原始材料变化时插入。

关键字段：

```text
snapshot_id
job_id
crawl_run_id
raw_payload
raw_payload_type
raw_payload_hash
content_hash
created_at
```

`content_hash` 基于公司、事业部、标题和 JD 主内容生成。对于 API JSON source，JD 主内容来自 JSON 中能直接映射的职责、要求、介绍等字段。对于 HTML source，JD 主内容可以在 extraction 后基于 Markdown 生成。

### job_extractions

`job_extractions` 是 extraction 任务记录。

字段：

```text
extraction_id
job_id
snapshot_id
extractor
extractor_version
llm_profile
model
status
output_markdown
error_code
error_message
attempt_count
created_at
```

`status` 只记录实际发生过的结果：

```text
succeeded
failed
skipped
```

不存 `pending`，因为 pending 可以通过查询推导出来。不存 `running`，MVP 先不做长任务状态管理。

## 11. Crawl 行为

`crawl run` 默认执行完整流水线：

```text
search -> fetch -> store
```

不做 extraction。

关闭判定：

- 某个 source 本次成功抓取后，未出现的该 source 岗位 `missing_count += 1`。
- `missing_count >= 2` 后标记为 `closed`。
- 如果 source 本身抓取失败，不更新该 source 下岗位的 `missing_count`。

`crawl run --all` 遇到单个 source 失败时继续跑其他 source，并返回 partial failure。

MVP 支持 dry run：

```bash
offerflow crawl run --source tencent-main --dry-run
offerflow crawl run --source tencent-main --dry-run --limit 10
```

Dry run 默认只输出摘要和前 5 条样本，不写 SQLite。

## 12. CLI 设计

CLI 默认输出 JSON，不输出人类表格。stdout 只输出最终 JSON，日志走 stderr 和 `.offerflow/logs/`。

统一响应 envelope：

```json
{
  "ok": true,
  "data": {},
  "warnings": [],
  "meta": {
    "command": "crawl run",
    "version": "0.1.0"
  }
}
```

错误响应：

```json
{
  "ok": false,
  "error": {
    "code": "DB_NOT_INITIALIZED",
    "message": "Local database is not initialized.",
    "details": {
      "db_path": ".offerflow/offerflow.sqlite"
    }
  },
  "warnings": [],
  "meta": {
    "command": "jobs list",
    "version": "0.1.0"
  }
}
```

不提供结构化 `hint` 字段，交给智能体根据错误码和描述判断下一步。

### Exit Codes

```text
0 = success
1 = user input or configuration error
2 = partial crawl/extract failure
3 = database or migration failure
```

stdout JSON 是语义通道，exit code 是 shell / runner 控制信号。

### Planned Commands

```bash
offerflow init
offerflow sources list
offerflow crawl run --all
offerflow crawl run --company tencent
offerflow crawl run --source tencent-main --channel campus
offerflow extract run --pending
offerflow extract run --failed
offerflow jobs list --new --since 24h
offerflow jobs show job_xxx
offerflow doctor
```

`jobs list` 返回轻量字段，不返回 payload 或 extraction markdown。

支持筛选：

```text
--company
--source
--channel
--status
--new --since
--changed --since
--closed --since
```

`jobs show` MVP 只支持 `job_id`：

```bash
offerflow jobs show job_xxx
offerflow jobs show job_xxx --with-extraction
```

默认不返回 extraction markdown，使用 `--with-extraction` 才返回。

## 13. 时间与参数

所有时间字段使用 UTC ISO 8601：

```text
2026-05-14T09:30:00Z
```

`--since` 支持：

```text
24h
7d
2026-05-14T00:00:00Z
```

不支持中文自然语言时间，由智能体负责转换。

## 14. 错误码

MVP 标准错误码：

```text
CONFIG_NOT_FOUND
DB_NOT_INITIALIZED
ADAPTER_NOT_FOUND
SOURCE_NOT_FOUND
FETCH_FAILED
EXTRACT_FAILED
MIGRATION_FAILED
INVALID_ARGUMENT
UNSUPPORTED_PAYLOAD_TYPE
```

## 15. Milestones

### M1: Project Skeleton

- uv + pyproject.toml
- Typer CLI
- JSON envelope
- SQLite migration runner
- config.yaml + .env handling

### M2: Storage Core

- companies / sources / crawl_runs / jobs / job_snapshots / job_extractions
- stable job_id
- source-level missing_count
- jobs list/show

### M3: Tencent Adapter

- tencent-main source
- campus/social/internship/unknown channel handling where available
- API JSON raw payload
- at least 20 JobRefs
- at least 10 detail raw payloads

### M4: ByteDance + Alibaba Adapters

- bytedance-main
- alibaba-main
- same adapter milestone as Tencent

### M5: MinerU-HTML Extractor

- optional dependency path
- OpenAI-compatible LLM profile
- default DeepSeek config
- extract run --pending
- extract run --failed
- output_markdown persisted in job_extractions

## 16. Adapter 验收口径

每个 MVP source 在正常网络下：

- Searcher 至少发现 20 条 JobRef。
- Fetcher 至少成功保存 10 条详情 raw_payload。
- 不要求 raw_description_text。
- 不要求程序化抽取 requirements / responsibilities / salary / skills。

这保证第一版重点放在抓取、落库、状态追踪和智能体可编排接口上。
