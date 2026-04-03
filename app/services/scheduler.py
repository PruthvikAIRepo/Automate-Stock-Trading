"""
Adaptive background scheduler for news scraping.

Each cycle:
1. Fetch RSS feeds -- only articles published SINCE last scrape
2. Dedup (URL + title similarity)
3. Classify ALL in ONE OpenAI call
4. Insert into DB

Schedule (IST):
  Market hours  (Mon-Fri 09:00-15:45) -> every 10 min
  Pre-market    (Mon-Fri 07:00-09:00) -> every 20 min
  Post-market   (Mon-Fri 15:45-20:00) -> every 30 min
  Night         (Mon-Fri 20:00-07:00) -> every 2 hours
  Weekends      (Sat-Sun all day)     -> every 3 hours
"""

import atexit
import logging
import os
import time as _time
from collections import Counter
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

log = logging.getLogger(__name__)

_scheduler = None
_IST = timezone(timedelta(hours=5, minutes=30))

# Single source of truth for timing
_last_scrape_at = None  # UTC datetime of last completed scrape


def _get_interval_minutes():
    now_ist = datetime.now(_IST)
    weekday = now_ist.weekday()
    time_val = now_ist.hour * 60 + now_ist.minute

    if weekday >= 5:
        return 180
    if 420 <= time_val < 540:
        return 20
    elif 540 <= time_val < 945:
        return 10
    elif 945 <= time_val < 1200:
        return 30
    else:
        return 120


def init_scheduler(app):
    global _scheduler

    if _scheduler is not None:
        try:
            if _scheduler.running:
                return
        except Exception:
            pass

    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        _adaptive_scrape,
        trigger="interval",
        minutes=10,
        id="news_scraper",
        replace_existing=True,
        next_run_time=datetime.now(),
    )
    _scheduler.start()
    log.info("News scheduler started (adaptive: 10m market / 20m pre / 30m post / 2h night / 3h weekend)")

    atexit.register(lambda: _scheduler.shutdown(wait=False))


def _adaptive_scrape():
    """Called every 10 min by APScheduler. Checks if enough time has passed, then scrapes."""
    global _last_scrape_at

    now = datetime.now(timezone.utc)
    interval = _get_interval_minutes()

    # Skip if not enough time has passed since last scrape
    if _last_scrape_at is not None:
        elapsed = (now - _last_scrape_at).total_seconds() / 60
        if elapsed < interval - 1:
            return

    # Determine time window for this cycle
    if _last_scrape_at is None:
        # First run ever: fetch articles from last 1 hour to seed the DB
        since = now - timedelta(hours=1)
        log.info("FIRST RUN -- fetching articles from last 1 hour")
    else:
        # Subsequent runs: only articles since last scrape (+2 min buffer for clock drift)
        since = _last_scrape_at - timedelta(minutes=2)
        mins_window = (now - since).total_seconds() / 60
        log.info("Fetching articles from last %.0f minutes", mins_window)

    # Mark scrape time AFTER calculating since, BEFORE running the cycle
    _last_scrape_at = now

    _run_cycle(since)


def _run_cycle(since):
    """Main pipeline: fetch -> dedup -> classify -> store."""
    try:
        from app.services.scraper import fetch_all_feeds, deduplicate
        from app.services.classifier import classify_articles
        from app.db import insert_articles

        interval = _get_interval_minutes()
        cycle_start = _time.time()
        log.info("=" * 60)
        log.info(
            "SCRAPE CYCLE START (IST: %s, interval: %dm)",
            datetime.now(_IST).strftime("%Y-%m-%d %H:%M:%S"), interval,
        )

        # Step 1: Fetch feeds -- time-filtered, only fresh articles
        t0 = _time.time()
        raw_articles = fetch_all_feeds(since=since)
        log.info("[Step 1/5] Fetched %d fresh articles from 10 feeds (%.1fs)", len(raw_articles), _time.time() - t0)
        if not raw_articles:
            log.info("No fresh articles -- cycle done")
            log.info("=" * 60)
            return

        # Step 2: Dedup (URL against DB + title similarity within batch)
        t0 = _time.time()
        new_articles = deduplicate(raw_articles)
        log.info("[Step 2/5] After dedup: %d -> %d articles (%.1fs)", len(raw_articles), len(new_articles), _time.time() - t0)
        if not new_articles:
            log.info("All articles already in DB -- cycle done")
            log.info("=" * 60)
            return

        # Step 3: Classify ALL in ONE OpenAI call (gpt-4.1-mini)
        new_articles.sort(key=lambda a: a.get("published_at", ""), reverse=True)
        t0 = _time.time()
        classified = classify_articles(new_articles)
        log.info("[Step 3/5] Classified %d articles in 1 API call (%.1fs)", len(classified), _time.time() - t0)

        # Step 4: Filter out IRRELEVANT
        relevant = [a for a in classified if a.get("category") != "IRRELEVANT"]
        skipped = len(classified) - len(relevant)
        if skipped:
            log.info("[Step 4/5] Dropped %d irrelevant, keeping %d", skipped, len(relevant))
        else:
            log.info("[Step 4/5] All %d articles relevant", len(relevant))

        # Step 5: Insert into DB
        t0 = _time.time()
        inserted = insert_articles(relevant)
        log.info("[Step 5/5] Inserted %d articles into DB (%.1fs)", inserted, _time.time() - t0)

        # Category breakdown
        cat_counts = Counter(a.get("category", "Uncategorized") for a in relevant)
        breakdown = " | ".join(f"{cat}: {cnt}" for cat, cnt in cat_counts.most_common())
        log.info("Categories: %s", breakdown if breakdown else "none")

        total_time = _time.time() - cycle_start
        log.info(
            "CYCLE COMPLETE in %.1fs | %d fetched -> %d new -> %d relevant -> %d inserted",
            total_time, len(raw_articles), len(new_articles), len(relevant), inserted,
        )
        log.info("=" * 60)

    except Exception as e:
        log.error("SCRAPE CYCLE FAILED: %s", e, exc_info=True)
