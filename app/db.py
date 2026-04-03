"""
SQLite database layer for StockPulse news articles.
Handles schema creation, article insertion with deduplication, and paginated queries.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone

_db_path = None


def init_db(app):
    """Create database and tables. Called once from create_app()."""
    global _db_path
    os.makedirs(app.instance_path, exist_ok=True)
    _db_path = os.path.join(app.instance_path, "stockpulse.db")

    conn = _get_connection()
    conn.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA busy_timeout=5000;

        CREATE TABLE IF NOT EXISTS articles (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            url            TEXT UNIQUE NOT NULL,
            title          TEXT NOT NULL,
            summary        TEXT DEFAULT '',
            source         TEXT NOT NULL,
            category       TEXT DEFAULT 'Uncategorized',
            sentiment      TEXT DEFAULT '',
            related_stocks TEXT DEFAULT '[]',
            published_at   TEXT NOT NULL,
            scraped_at     TEXT NOT NULL,
            is_breaking    INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at DESC);
        CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category);
    """)
    conn.close()


def _get_connection():
    """Return a new SQLite connection. Each thread must call this independently."""
    conn = sqlite3.connect(_db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def insert_articles(articles):
    """
    Batch insert articles. Duplicates (by URL) are silently skipped.
    Returns count of actually inserted rows.
    """
    if not articles:
        return 0

    conn = _get_connection()
    before = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    conn.executemany(
        """INSERT OR IGNORE INTO articles
           (url, title, summary, source, category, sentiment, related_stocks, published_at, scraped_at, is_breaking)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                a["url"],
                a["title"],
                a.get("summary", ""),
                a["source"],
                a.get("category", "Uncategorized"),
                a.get("sentiment", ""),
                json.dumps(a.get("related_stocks", [])),
                a["published_at"],
                a.get("scraped_at", datetime.now(timezone.utc).isoformat()),
                1 if a.get("is_breaking") else 0,
            )
            for a in articles
        ],
    )
    conn.commit()
    after = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    conn.close()
    return after - before


def get_articles(page=1, per_page=20, category=None):
    """
    Return (articles_list, total_count) for pagination.
    Articles ordered by published_at DESC.
    """
    conn = _get_connection()

    where = ""
    params = []
    if category and category != "all":
        where = "WHERE category = ?"
        params.append(category)

    total = conn.execute(
        f"SELECT COUNT(*) FROM articles {where}", params
    ).fetchone()[0]

    offset = (page - 1) * per_page
    rows = conn.execute(
        f"""SELECT * FROM articles {where}
            ORDER BY published_at DESC
            LIMIT ? OFFSET ?""",
        params + [per_page, offset],
    ).fetchall()

    articles = []
    for row in rows:
        article = dict(row)
        article["related_stocks"] = json.loads(article["related_stocks"])
        articles.append(article)

    conn.close()
    return articles, total


def get_existing_urls(urls):
    """Return set of URLs that already exist in the database."""
    if not urls:
        return set()

    conn = _get_connection()
    placeholders = ",".join("?" for _ in urls)
    rows = conn.execute(
        f"SELECT url FROM articles WHERE url IN ({placeholders})", list(urls)
    ).fetchall()
    conn.close()
    return {row["url"] for row in rows}
