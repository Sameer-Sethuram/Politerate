-- backend/db/schema.sql
--
-- Politerate SQLite schema. Loaded by backend/db/connection.py:init_db().
--
-- Merges our news-clustering tables (clusters, seen_urls, scraped_articles_archive,
-- daily_snapshots, metadata) with Sarah's Text Analyzer fields (analysis JSON
-- blobs, bias_label, FTS5 full-text search) in a single articles table.

-- ---------------------------------------------------------------------------
-- articles: every scraped OR user-submitted article we've seen
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE,
    url_hash TEXT UNIQUE,
    title TEXT,
    source TEXT,
    author TEXT,
    published_at TIMESTAMP,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Content
    text TEXT,
    word_count INTEGER,

    -- Credibility (pipeline filter output)
    credibility_score REAL DEFAULT 1.0,
    credibility_label TEXT DEFAULT 'unknown',

    -- Cluster linkage (news-page grouping)
    cluster_id TEXT,

    -- Analysis results (from DeBERTa multi-head analyzer)
    analysis_json TEXT,
    article_json TEXT,
    bias_label TEXT,
    dominant_emotion TEXT,
    subjectivity_ratio REAL,
    analysis_model_version TEXT,
    analyzed_at TIMESTAMP,
    analysis_status TEXT DEFAULT 'pending',

    -- Per-article BART summary (for future phase)
    summary TEXT,
    summary_model_version TEXT,
    summarized_at TIMESTAMP,

    -- Provenance: 'scraped' (news pipeline) vs 'user_submitted' (/api/analyze)
    source_type TEXT DEFAULT 'scraped'
);

-- Indexes for the articles table live in connection.py so they run AFTER
-- the column migrations (otherwise they reference columns that don't
-- exist yet on older DB files).

-- ---------------------------------------------------------------------------
-- clusters: topic groupings from the news pipeline
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS clusters (
    id TEXT PRIMARY KEY,
    summary TEXT,
    highlighted_summary TEXT,
    sources TEXT,
    urls TEXT,
    titles TEXT,
    terms TEXT,
    article_count INTEGER,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- metadata: singleton keys (e.g. last_refresh)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- ---------------------------------------------------------------------------
-- seen_urls: URL dedup between hourly refreshes
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS seen_urls (
    url TEXT PRIMARY KEY,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- scraped_articles_archive: 7-day rolling cache of full article bodies
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scraped_articles_archive (
    url TEXT PRIMARY KEY,
    title TEXT,
    source TEXT,
    text TEXT,
    authors TEXT,
    publish_date TEXT,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    analysis_json 
);

CREATE INDEX IF NOT EXISTS idx_archive_scraped_at ON scraped_articles_archive(scraped_at);

-- ---------------------------------------------------------------------------
-- daily_snapshots: end-of-day cluster snapshots for the Archive page
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS daily_snapshots (
    snapshot_date TEXT PRIMARY KEY,
    snapshot_json TEXT,
    article_count INTEGER,
    cluster_count INTEGER,
    source_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
