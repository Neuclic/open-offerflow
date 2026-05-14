CREATE TABLE IF NOT EXISTS companies (
    company_id TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    company_id TEXT NOT NULL,
    adapter TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (company_id) REFERENCES companies(company_id)
);

CREATE TABLE IF NOT EXISTS crawl_runs (
    crawl_run_id TEXT PRIMARY KEY,
    source_id TEXT,
    company_id TEXT,
    channel TEXT,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    jobs_seen INTEGER NOT NULL DEFAULT 0,
    jobs_changed INTEGER NOT NULL DEFAULT 0,
    jobs_failed INTEGER NOT NULL DEFAULT 0,
    error_code TEXT,
    error_message TEXT,
    FOREIGN KEY (source_id) REFERENCES sources(source_id),
    FOREIGN KEY (company_id) REFERENCES companies(company_id)
);

CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    company_name TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_job_id TEXT,
    title TEXT,
    location TEXT,
    business_unit TEXT,
    channel TEXT NOT NULL DEFAULT 'unknown',
    detail_url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    missing_count INTEGER NOT NULL DEFAULT 0,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    closed_at TEXT,
    current_snapshot_id TEXT,
    content_hash TEXT,
    FOREIGN KEY (company_id) REFERENCES companies(company_id),
    FOREIGN KEY (source_id) REFERENCES sources(source_id)
);

CREATE INDEX IF NOT EXISTS idx_jobs_source_status ON jobs(source_id, status);
CREATE INDEX IF NOT EXISTS idx_jobs_company_channel ON jobs(company_id, channel);
CREATE INDEX IF NOT EXISTS idx_jobs_seen ON jobs(first_seen_at, last_seen_at);

CREATE TABLE IF NOT EXISTS job_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    crawl_run_id TEXT,
    raw_payload TEXT NOT NULL,
    raw_payload_type TEXT NOT NULL CHECK(raw_payload_type IN ('json', 'html')),
    raw_payload_hash TEXT NOT NULL,
    content_hash TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id),
    FOREIGN KEY (crawl_run_id) REFERENCES crawl_runs(crawl_run_id)
);

CREATE INDEX IF NOT EXISTS idx_job_snapshots_job ON job_snapshots(job_id, created_at);

CREATE TABLE IF NOT EXISTS job_extractions (
    extraction_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    snapshot_id TEXT NOT NULL,
    extractor TEXT NOT NULL,
    extractor_version TEXT,
    llm_profile TEXT,
    model TEXT,
    status TEXT NOT NULL CHECK(status IN ('succeeded', 'failed', 'skipped')),
    output_markdown TEXT,
    error_code TEXT,
    error_message TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id),
    FOREIGN KEY (snapshot_id) REFERENCES job_snapshots(snapshot_id)
);

CREATE INDEX IF NOT EXISTS idx_job_extractions_snapshot ON job_extractions(snapshot_id, status);
