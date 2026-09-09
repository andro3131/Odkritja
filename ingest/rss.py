"""RSS plasti — zastonj, vedno."""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser

from ingest.config import RSS_FEEDS


def _strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _entry_dt(entry: Any) -> datetime | None:
    for attr in ("published", "updated"):
        raw = getattr(entry, attr, None)
        if not raw:
            continue
        try:
            dt = parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (TypeError, ValueError, OverflowError):
            continue
    parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if parsed:
        return datetime.fromtimestamp(time.mktime(parsed), tz=timezone.utc)
    return None


def fetch_rss(hours: int = 36, per_feed: int = 8) -> list[dict[str, Any]]:
    """Vrni surove zadetke zadnjih `hours` ur."""
    cutoff = datetime.now(timezone.utc).timestamp() - hours * 3600
    out: list[dict[str, Any]] = []
    for fid, url, teme in RSS_FEEDS:
        parsed = feedparser.parse(url)
        count = 0
        for entry in parsed.entries:
            if count >= per_feed:
                break
            dt = _entry_dt(entry)
            if dt and dt.timestamp() < cutoff:
                continue
            link = (entry.get("link") or "").strip()
            if not link:
                continue
            title = (entry.get("title") or "").strip()
            summary = (entry.get("summary") or entry.get("description") or "").strip()
            if "<" in summary:
                summary = _strip_html(summary)
            out.append(
                {
                    "id": f"rss-{fid}-{link}",
                    "tip": "rss",
                    "feed": fid,
                    "naslov": title,
                    "povzetek": summary[:1200],
                    "url": link,
                    "teme": list(teme),
                    "published": dt.isoformat() if dt else None,
                }
            )
            count += 1
    return out
