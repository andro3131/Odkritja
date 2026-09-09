#!/usr/bin/env python3
"""Dnevni ingest: RSS + inbox + opcijski x_search → content/dnevi/YYYY-MM-DD.json."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from ingest.config import DNEVI, MANIFEST, USAGE, WATCHLIST, daily_cost_cap  # noqa: E402
from ingest.inbox import archive_inbox, enrich_inbox, parse_inbox  # noqa: E402
from ingest.predictions import (  # noqa: E402
    propose_weekly,
    score_predictions,
    sunday_recap,
    update_watchlist,
)
from ingest.rss import fetch_rss  # noqa: E402
from ingest.synthesize import drop_dupes, load_recent_titles, synthesize  # noqa: E402
from ingest.x_search import fetch_x_search  # noqa: E402


def today_lj() -> date:
    return datetime.now(ZoneInfo("Europe/Ljubljana")).date()


def load_usage() -> dict:
    if USAGE.exists():
        return json.loads(USAGE.read_text(encoding="utf-8"))
    return {"cap_usd_na_dan": daily_cost_cap(), "dnevi": []}


def spent_today(usage: dict, day: date) -> float:
    return sum(
        float(d.get("estimated_usd") or 0)
        for d in usage.get("dnevi") or []
        if d.get("date") == day.isoformat()
    )


def write_usage(usage: dict, day: date, meta: dict) -> None:
    usage.setdefault("dnevi", [])
    usage["cap_usd_na_dan"] = daily_cost_cap()
    usage["dnevi"] = [d for d in usage["dnevi"] if d.get("date") != day.isoformat()]
    usage["dnevi"].append(
        {
            "date": day.isoformat(),
            "skipped": meta.get("skipped", False),
            "reason": meta.get("reason"),
            "calls": meta.get("calls", 0),
            "posts_est": meta.get("posts_est", 0),
            "estimated_usd": meta.get("estimated_usd", 0),
            "handles": meta.get("handles") or [],
        }
    )
    usage["dnevi"] = usage["dnevi"][-90:]
    USAGE.write_text(json.dumps(usage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_manifest() -> None:
    dnevi = sorted(p.stem for p in DNEVI.glob("*.json"))
    MANIFEST.write_text(
        json.dumps({"dnevi": dnevi}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def watch_ids() -> list[str]:
    if not WATCHLIST.exists():
        return []
    data = json.loads(WATCHLIST.read_text(encoding="utf-8"))
    return [t["id"] for t in data.get("teme") or [] if t.get("id")]


def main() -> int:
    ap = argparse.ArgumentParser(description="Odkritja dnevni ingest")
    ap.add_argument("--no-x", action="store_true", help="Preskoči x_search")
    ap.add_argument("--dry", action="store_true", help="Ne piši datotek")
    ap.add_argument("--date", help="YYYY-MM-DD (privzeto danes LJ)")
    args = ap.parse_args()

    day = date.fromisoformat(args.date) if args.date else today_lj()
    DNEVI.mkdir(parents=True, exist_ok=True)

    print(f"== Odkritja ingest {day.isoformat()} ==")
    rss = fetch_rss()
    print(f"RSS: {len(rss)}")
    inbox = enrich_inbox(parse_inbox())
    print(f"Inbox: {len(inbox)}")

    x_items: list = []
    x_meta = {"skipped": True, "reason": "--no-x", "calls": 0, "estimated_usd": 0, "handles": []}
    usage = load_usage()
    if not args.no_x:
        x_items, x_meta = fetch_x_search(day, daily_cost_cap(), spent_today(usage, day))
        print(f"X: {len(x_items)} ({x_meta.get('reason') or 'ok'}, ~${x_meta.get('estimated_usd') or 0})")
    else:
        print("X: preskočeno")

    items = drop_dupes(inbox + x_items + rss, load_recent_titles(day))
    print(f"Po dedup 14 dni: {len(items)}")

    day_doc = synthesize(day, items, watch_ids())
    recap = sunday_recap(day)
    if recap:
        day_doc["recap"] = recap
        print("Recap: da")

    if args.dry:
        print(json.dumps({k: day_doc[k] for k in ("naslov_dneva", "kartice") if k in day_doc}, ensure_ascii=False)[:1500])
        print(f"(dry) kartic: {len(day_doc.get('kartice') or [])}")
        return 0

    out = DNEVI / f"{day.isoformat()}.json"
    out.write_text(json.dumps(day_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    update_watchlist(day, day_doc.get("kartice") or [])
    scored = score_predictions(day)
    if scored:
        print("Napovedi:", "; ".join(scored))
    added = propose_weekly(day)
    if added:
        print(f"Nove napovedi: {len(added)}")
    if inbox:
        archive_inbox()
    write_usage(usage, day, x_meta)
    write_manifest()
    print(f"Zapisano {out} ({len(day_doc.get('kartice') or [])} kartic)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
