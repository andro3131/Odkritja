"""Poti, RSS, X handle rotacija, stroški."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
DNEVI = CONTENT / "dnevi"
WATCHLIST = CONTENT / "watchlist.json"
NAPOVEDI = CONTENT / "napovedi.json"
INBOX = CONTENT / "inbox.md"
INBOX_DONE = CONTENT / "inbox-done.md"
USAGE = CONTENT / "usage.json"
MANIFEST = CONTENT / "manifest.json"

X_SEARCH_PER_POST_FROM = date(2026, 9, 21)

RSS_FEEDS = [
    ("arxiv-cs-ai", "https://rss.arxiv.org/rss/cs.AI", ["ai"]),
    ("arxiv-cs-ro", "https://rss.arxiv.org/rss/cs.RO", ["robotika", "ai"]),
    ("arxiv-qbio", "https://rss.arxiv.org/rss/q-bio", ["medicina"]),
    ("biorxiv", "https://connect.biorxiv.org/biorxiv_xml.php?subject=all", ["medicina"]),
    ("nature", "https://www.nature.com/nature.rss", ["medicina", "fizika"]),
    ("science", "https://www.science.org/rss/news_current.xml", ["medicina", "fizika"]),
    ("openai", "https://openai.com/blog/rss.xml", ["ai"]),
    ("deepmind", "https://deepmind.google/blog/rss.xml", ["ai"]),
    ("xai-blog", "https://x.ai/blog/rss.xml", ["ai"]),
    ("nasa", "https://www.nasa.gov/news-release/feed/", ["spacex"]),
    ("spaceflightnow", "https://spaceflightnow.com/feed/", ["spacex"]),
    ("tesla-ir", "https://ir.tesla.com/press-release/rss", ["tesla"]),
]

HANDLES_SPACEX_TESLA = [
    "elonmusk",
    "SpaceX",
    "Tesla",
    "teslaeurope",
    "NASASpaceflight",
    "NASA",
    "Teslarati",
    "SawyerMerritt",
    "WholeMarsBlog",
    "nextspaceflight",
    "SpaceflightNow",
    "NASAKennedy",
    "boringcompany",
    "Tesla_AI",
]

HANDLES_AI_MED = [
    "OpenAI",
    "xai",
    "GoogleDeepMind",
    "AnthropicAI",
    "demishassabis",
    "Nature",
    "NatureMedicine",
    "NEJM",
    "InsilicoMed",
    "NVIDIA",
    "Figure_robot",
    "BostonDynamics",
    "ScienceMagazine",
    "karpathy",
    "sama",
    "DrBenGoertzel",
    "DeepMind",
    "NaturePortfolio",
]


def unique_handles(seq: list[str], limit: int = 20) -> list[str]:
    seen: list[str] = []
    for h in seq:
        h = h.lstrip("@")
        if h not in seen:
            seen.append(h)
        if len(seen) >= limit:
            break
    return seen


def handles_for_weekday(weekday: int) -> list[str]:
    """0=pon … 6=ned. Pon/sre/pet SpaceX+Tesla; tor/čet/sob AI+med; ned mix."""
    a = unique_handles(HANDLES_SPACEX_TESLA, 20)
    b = unique_handles(HANDLES_AI_MED, 20)
    if weekday in (0, 2, 4):
        return a[:20]
    if weekday in (1, 3, 5):
        return b[:20]
    return unique_handles(a[:10] + b[:10], 20)


def daily_cost_cap() -> float:
    raw = os.environ.get("DAILY_COST_CAP", "0.15")
    try:
        return float(raw)
    except ValueError:
        return 0.15


def estimate_x_search_usd(today: date, posts_fetched: int, calls: int = 1) -> float:
    if today >= X_SEARCH_PER_POST_FROM:
        return posts_fetched * 0.005
    return calls * 0.005
