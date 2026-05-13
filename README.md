# Open OfferFlow

[中文](#中文) | [English](#english)

## 中文

一个面向学生和求职者的本地优先岗位情报工具，用来追踪目标公司官网上快速变化的岗位机会。

Open OfferFlow 是一个本地优先的命令行工具包，用于监控目标公司的招聘官网、抓取职位描述，并将结构化岗位数据存入本地数据库，供智能体驱动的求职工作流使用。

状态：立项与最小可行版本设计阶段。

## 最小可行范围

- 目标公司招聘官网的来源适配器
- 可重复执行的抓取命令，方便由定时任务或智能体运行环境调度
- 职位描述解析、字段标准化和链接去重
- 本地 SQLite 数据库存储
- 新增、变更、关闭岗位的状态追踪
- 面向编程智能体和自动化运行环境的命令行优先接入方式

抓取结果默认落在本地 SQLite 数据库中。后续的看板、MCP 工具、精选岗位流和简历匹配都基于这份本地数据展开。

## 计划中的命令行

```bash
offerflow init
offerflow sources list
offerflow sources add --company Tencent --adapter tencent
offerflow crawl run --source Tencent
offerflow crawl run --all
offerflow jobs list --new --since 24h
offerflow jobs show <job-id>
offerflow doctor
```

## 智能体接入

Open OfferFlow 设计为可被编程智能体和自动化运行环境调用。命令行是能力源头，Skill instructions 和 MCP tools 是围绕本地命令行与 SQLite 数据库的薄接入层。

## 适配目标

初始目标：

Alibaba, Tencent, ByteDance, Meituan, JD, Baidu

后续目标：

NetEase, Xiaomi, Kuaishou, Pinduoduo, Ant Group, Didi

## 路线图

1. Crawl first  
   先构建稳定的来源适配器，并把结构化职位描述数据可靠落到本地。

2. Match later  
   在本地职位描述数据之上增加简历感知的订阅、匹配打分和精选岗位流。

3. Apply assistant  
   在数据层稳定后，探索需要用户确认的申请辅助流程。

## 规划目录

```text
open-offerflow/
├─ src/offerflow/     # 命令行核心、抓取、解析、存储
├─ adapters/          # 公司招聘官网适配器
├─ skills/            # 智能体技能说明
├─ mcp/               # MCP 服务和工具封装
├─ docs/
└─ tests/
```

## 许可证

MIT

---

## English

# Open OfferFlow

A local-first job intelligence toolkit for students and job seekers who track fast-moving roles across target company career sites.

Open OfferFlow is a local-first CLI toolkit for monitoring target company career pages, fetching job descriptions, and storing structured job data for agent-driven job search workflows.

Status: Planning and MVP design.

## MVP Scope

- Source adapters for target company career sites
- Repeatable crawl commands that can be scheduled by cron, Task Scheduler, or agent runtimes
- JD parsing, field normalization, and URL deduplication
- Local SQLite storage
- Job status tracking for new, changed, and closed roles
- CLI-first access for coding agents and automation runtimes

All crawled data is stored locally in SQLite. Future dashboards, MCP tools, curated feeds, and resume matching will be built on top of this local data layer.

## Planned CLI

```bash
offerflow init
offerflow sources list
offerflow sources add --company Tencent --adapter tencent
offerflow crawl run --source Tencent
offerflow crawl run --all
offerflow jobs list --new --since 24h
offerflow jobs show <job-id>
offerflow doctor
```

## Agent Integration

Open OfferFlow is designed to be called by coding agents and automation runtimes. The CLI is the source of truth; Skill instructions and MCP tools are thin integration layers around the local CLI and SQLite database.

## Adapter Targets

Initial targets:

Alibaba, Tencent, ByteDance, Meituan, JD, Baidu

Planned next:

NetEase, Xiaomi, Kuaishou, Pinduoduo, Ant Group, Didi

## Roadmap

1. Crawl first  
   Build reliable source adapters and store structured JD data locally.

2. Match later  
   Add resume-aware subscriptions, matching scores, and curated feeds on top of stored JD data.

3. Apply assistant  
   Explore user-confirmed application assistance after the data layer is stable.

## Planned Structure

```text
open-offerflow/
├─ src/offerflow/     # CLI core, crawler, parser, storage
├─ adapters/          # company career site adapters
├─ skills/            # agent skill instructions
├─ mcp/               # MCP server and tool wrappers
├─ docs/
└─ tests/
```

## License

MIT
