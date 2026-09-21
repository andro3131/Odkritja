"""Prilepek URL iz content/inbox.md."""

from __future__ import annotations

import re
from typing import Any
from urllib.request import Request, urlopen

from ingest.config import INBOX, INBOX_DONE

URL_RE = re.compile(r"https?://[^\s)>]+")


def parse_inbox() -> list[dict[str, Any]]:
    if not INBOX.exists():
        return []
    text = INBOX.read_text(encoding="utf-8")
    items: list[dict[str, Any]] = []
    pending_note = ""
    in_fence = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not line or line.startswith("#"):
            continue
        if line.startswith("Prilepi") or line.startswith("Primer") or line.startswith("ali "):
            continue
        if "…" in line or "..." in line:
            continue
        m = URL_RE.search(line)
        if m:
            url = m.group(0).rstrip(".,;")
            items.append(
                {
                    "id": f"inbox-{url}",
                    "tip": "inbox",
                    "naslov": pending_note or url,
                    "povzetek": pending_note,
                    "url": url,
                    "teme": _teme_from_url(url),
                    "note": pending_note,
                }
            )
            pending_note = ""
        else:
            pending_note = line
    return items


def fetch_title(url: str, timeout: int = 12) -> str:
    try:
        req = Request(url, headers={"User-Agent": "VremenkoRadar/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            html = resp.read(80_000).decode("utf-8", errors="ignore")
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        if m:
            title = re.sub(r"\s+", " ", m.group(1)).strip()
            return title[:200]
    except Exception:
        pass
    return url


def enrich_inbox(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for it in items:
        if it["naslov"] == it["url"] or it["naslov"].startswith("http"):
            it["naslov"] = fetch_title(it["url"])
        if not it.get("povzetek"):
            it["povzetek"] = it["naslov"]
    return items


def archive_inbox() -> None:
    if not INBOX.exists():
        return
    raw = INBOX.read_text(encoding="utf-8")
    urls = URL_RE.findall(raw)
    if not urls:
        return
    stamp = "\n".join(urls)
    prev = INBOX_DONE.read_text(encoding="utf-8") if INBOX_DONE.exists() else "# Obdelano\n\n"
    INBOX_DONE.write_text(prev.rstrip() + "\n" + stamp + "\n", encoding="utf-8")
    INBOX.write_text(
        "# Inbox\n\nPrilepi en URL na vrstico. Opomba v vrstici pred URL.\n",
        encoding="utf-8",
    )


def _teme_from_url(url: str) -> list[str]:
    u = url.lower()
    teme: list[str] = []
    if any(x in u for x in ("tesla", "fsd")):
        teme.append("tesla")
    if any(x in u for x in ("spacex", "starship", "nasa")):
        teme.append("spacex")
    if any(x in u for x in ("openai", "x.ai", "deepmind", "anthropic", "gpt")):
        teme.append("ai")
    if any(x in u for x in ("nature", "nih.gov", "clinicaltrials", "pubmed", "biorxiv")):
        teme.append("medicina")
    return teme or ["ai"]
