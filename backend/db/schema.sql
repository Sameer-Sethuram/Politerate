-- Main articles table
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE,
    url_hash TEXT UNIQUE NOT NULL,
    title TEXT,
    source TEXT,
    author TEXT,
    published_at TIMESTAMP,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Content
    content TEXT NOT NULL,
    word_count INTEGER,
    
    -- Analysis results
    analysis_json TEXT,              -- per-chunk predictions
    article_json TEXT,               -- article-level aggregations
    bias_label TEXT,
    dominant_emotion TEXT,
    subjectivity_ratio REAL,
    analysis_model_version TEXT,
    analyzed_at TIMESTAMP,
    analysis_status TEXT DEFAULT 'pending',
    
    -- Summary (for Phase 3)
    summary TEXT,
    summary_model_version TEXT,
    summarized_at TIMESTAMP,
    
    -- Source tracking
    source_type TEXT DEFAULT 'user_submitted'
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source);
CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_url_hash ON articles(url_hash);
CREATE INDEX IF NOT EXISTS idx_articles_bias ON articles(bias_label);
CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(analysis_status);

-- Full-text search (Phase 4, but set up now)
CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
    title, content,
    content=articles,
    content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS articles_fts_insert AFTER INSERT ON articles BEGIN
    INSERT INTO articles_fts(rowid, title, content)
    VALUES (new.id, new.title, new.content);
END;

CREATE TRIGGER IF NOT EXISTS articles_fts_update AFTER UPDATE ON articles BEGIN
    UPDATE articles_fts SET title = new.title, content = new.content
    WHERE rowid = new.id;
END;

CREATE TRIGGER IF NOT EXISTS articles_fts_delete AFTER DELETE ON articles BEGIN
    DELETE FROM articles_fts WHERE rowid = old.id;
END;