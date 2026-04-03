"""
RSS feed scraper for Indian stock market news.
Fetches from 10 trusted sources, keeps only articles published after a cutoff time,
deduplicates against DB + title similarity.
"""

import logging
import re
import socket
from datetime import datetime, timezone, timedelta

import feedparser

from app.db import get_existing_urls

log = logging.getLogger(__name__)

FEEDS = {
    # Economic Times — 3 feeds (default, markets, industry)
    "https://economictimes.indiatimes.com/rssfeedsdefault.cms": "Economic Times",
    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms": "ET Markets",
    "https://economictimes.indiatimes.com/industry/rssfeeds/13352306.cms": "ET Industry",
    # LiveMint — 2 feeds (markets, companies)
    "https://www.livemint.com/rss/markets": "LiveMint",
    "https://www.livemint.com/rss/companies": "LiveMint Companies",
    # Hindu BusinessLine — high-frequency updates
    "https://www.thehindubusinessline.com/feeder/default.rss": "Hindu BusinessLine",
    # Investing.com India — global perspective on Indian markets
    "https://in.investing.com/rss/news_25.rss": "Investing.com India",
    # NDTV Profit
    "https://feeds.feedburner.com/ndtvprofit-latest": "NDTV Profit",
    # Zerodha Pulse — curated market news
    "http://pulse.zerodha.com/feed.php": "Zerodha Pulse",
    # ET Top Stories — broader coverage
    "https://economictimes.indiatimes.com/rssfeedstopstories.cms": "ET Top Stories",
}

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_STOP_WORDS = frozenset(
    "a an the is are was were be been being in on at to for of and or but "
    "by with from as it its this that these those has have had do does did "
    "will would shall should may might can could".split()
)


def fetch_all_feeds(since):
    """
    Fetch all RSS feeds. Only keep articles published AFTER `since` (datetime, UTC).
    Returns list of raw article dicts.
    """
    all_articles = []
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(15)

    for feed_url, source_name in FEEDS.items():
        try:
            feed = feedparser.parse(feed_url, request_headers={"User-Agent": _UA})

            if hasattr(feed, "status") and feed.status >= 400:
                log.warning("Feed %s returned HTTP %s", feed_url, feed.status)
                continue

            kept = 0
            skipped_old = 0
            for entry in feed.entries:
                article = _parse_entry(entry, feed_url, source_name, since)
                if article:
                    all_articles.append(article)
                    kept += 1
                else:
                    skipped_old += 1

            log.info(
                "%s: %d new, %d old (skipped), %d total in feed",
                source_name, kept, skipped_old, len(feed.entries),
            )

        except Exception as e:
            log.error("Error fetching %s: %s", feed_url, e)

    socket.setdefaulttimeout(old_timeout)
    return all_articles


def deduplicate(raw_articles):
    """Remove articles whose URLs already exist in the DB, then remove title-similar duplicates."""
    if not raw_articles:
        return []

    # Layer 1: URL dedup against database
    urls = {a["url"] for a in raw_articles}
    existing = get_existing_urls(urls)
    new_articles = [a for a in raw_articles if a["url"] not in existing]
    log.info("URL dedup: %d total, %d already in DB, %d new", len(raw_articles), len(existing), len(new_articles))

    # Layer 2: Title similarity dedup within the batch
    if len(new_articles) <= 1:
        return new_articles

    unique = []
    seen_fingerprints = []

    for article in new_articles:
        fp = _title_fingerprint(article["title"])
        is_dup = False
        for seen_fp in seen_fingerprints:
            if _jaccard_similarity(fp, seen_fp) > 0.70:
                is_dup = True
                break
        if not is_dup:
            unique.append(article)
            seen_fingerprints.append(fp)

    dropped = len(new_articles) - len(unique)
    if dropped:
        log.info("Title dedup: dropped %d similar articles, %d remain", dropped, len(unique))
    return unique


def _title_fingerprint(title):
    words = re.sub(r"[^a-z0-9\s]", "", title.lower()).split()
    return frozenset(w for w in words if w not in _STOP_WORDS and len(w) > 1)


def _jaccard_similarity(set_a, set_b):
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 0.0


def _parse_entry(entry, feed_url, source_name, since):
    """
    Parse one RSS entry. Returns None if:
    - missing url/title
    - published BEFORE the `since` cutoff
    """
    url = getattr(entry, "link", None)
    if not url:
        return None

    title = getattr(entry, "title", "").strip()
    if not title:
        return None

    # Parse published date
    published_at = _parse_date(entry)

    # TIME FILTER: skip articles older than `since`
    now = datetime.now(timezone.utc)
    try:
        pub_dt = datetime.fromisoformat(published_at)
        if pub_dt.tzinfo is None:
            pub_dt = pub_dt.replace(tzinfo=timezone.utc)
        if pub_dt < since:
            return None
        is_breaking = (now - pub_dt) < timedelta(hours=1)
    except (ValueError, TypeError):
        # Can't parse date — skip it, don't risk old article
        return None

    # Summary — strip HTML tags
    raw_summary = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
    summary = _HTML_TAG_RE.sub("", raw_summary).strip()
    if len(summary) > 500:
        summary = summary[:497] + "..."

    return {
        "url": url,
        "title": title,
        "summary": summary,
        "source": source_name,
        "feed_url": feed_url,
        "published_at": published_at,
        "scraped_at": now.isoformat(),
        "is_breaking": is_breaking,
        "category": "Uncategorized",
        "related_stocks": [],
    }


def _parse_date(entry):
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            return dt.isoformat()
        except (ValueError, TypeError):
            pass

    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        try:
            dt = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
            return dt.isoformat()
        except (ValueError, TypeError):
            pass

    return datetime.now(timezone.utc).isoformat()
