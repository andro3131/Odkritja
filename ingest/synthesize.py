"""Sintaza kartic. Vir (URL) je obvezen. Brez izmišljevanja."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import date, timedelta
from typing import Any
from unicodedata import normalize

from ingest.config import DNEVI

SYNTH_PROMPT = """Si urednik osebnega radarja odkritij (medicina, AI, SpaceX, Tesla, robotika, fizika).
Jezik: živa slovenščina, suha ironija dovoljena. V stavku ~1 angleška beseda poleg lastnih imen.
Ostane EN: FSD, Starship, SecUnit ni tu, feed, paper, Phase III, OTA.

STROGO:
- Piši SAMO iz spodnjih virov. Ne izmišljuj datumov, imen zdravil, številk.
- Vsaka kartica MORA imeti vsaj en url iz virov.
- 5–12 stavkov v povzetek_sl, ne tweet.
- Max 12 kartic. Izberi samo zares novo. Duplikate spusti.
- status: paper | uradno | govorica | napoved
- teme: podmnožica ai, medicina, spacex, tesla, robotika, fizika
- watch_id če pasuje na watchlist, sicer null
- zaupanje 1–5

Watchlist id-ji: {watch_ids}

Vrni SAMO JSON:
{{"naslov_dneva": "...", "kartice": [{{"id": "YYYY-MM-DD-slug", "date": "{day}", "teme": [], "naslov": "", "povzetek_sl": "", "zakaj_je_vazno": "", "status": "uradno", "zaupanje": 4, "watch_id": null, "viri": [{{"tip": "rss", "handle": null, "naslov": "", "url": ""}}]}}]}}

Viri:
{sources}
"""


def _slug(s: str) -> str:
    s = normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower()).strip("-")
    return s[:60] or "kartica"


def _norm_title(s: str) -> str:
    s = normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def load_recent_titles(today: date, days: int = 14) -> set[str]:
    out: set[str] = set()
    for i in range(1, days + 1):
        p = DNEVI / f"{(today - timedelta(days=i)).isoformat()}.json"
        if not p.exists():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        for c in data.get("kartice") or []:
            t = _norm_title(c.get("naslov") or "")
            if t:
                out.add(t)
    return out


def drop_dupes(items: list[dict[str, Any]], seen: set[str]) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    local: set[str] = set()
    urls: set[str] = set()
    for it in items:
        url = (it.get("url") or "").split("?")[0]
        title = _norm_title(it.get("naslov") or "")
        if url and url in urls:
            continue
        if title and (title in seen or title in local):
            continue
        if url:
            urls.add(url)
        if title:
            local.add(title)
        kept.append(it)
    return kept


def fallback_cards(day: date, items: list[dict[str, Any]]) -> dict[str, Any]:
    kartice = []
    for it in items[:12]:
        url = it.get("url") or ""
        if not url.startswith("http"):
            continue
        naslov = it.get("naslov") or url
        pov = (it.get("povzetek") or naslov).strip()
        if len(pov) < 80:
            pov = f"{naslov}. Vir je RSS/inbox brez modela — to ni poln slovenski opis, samo sled. Odpri povezavo."
        kartice.append(
            {
                "id": f"{day.isoformat()}-{_slug(naslov)}",
                "date": day.isoformat(),
                "teme": it.get("teme") or ["ai"],
                "naslov": naslov[:180],
                "povzetek_sl": pov[:1800],
                "zakaj_je_vazno": it.get("note") or "Brez LLM sintaze (ni API ključa).",
                "status": "paper" if it.get("tip") == "rss" else "govorica",
                "zaupanje": 2,
                "watch_id": None,
                "viri": [
                    {
                        "tip": it.get("tip") or "web",
                        "handle": it.get("handle"),
                        "naslov": naslov[:120],
                        "url": url,
                    }
                ],
            }
        )
    return {
        "date": day.isoformat(),
        "naslov_dneva": "Surovi zadetki (brez sintaze)" if kartice else "Tiho",
        "recap": None,
        "kartice": kartice,
    }


def _http_json(url: str, body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _call_xai(prompt: str) -> str:
    key = os.environ.get("XAI_API_KEY", "").strip()
    if not key:
        return ""
    model = os.environ.get("XAI_MODEL", "grok-4.3")
    data = _http_json(
        "https://api.x.ai/v1/chat/completions",
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
        },
        {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
    )
    return data["choices"][0]["message"]["content"]


def _call_gemini(prompt: str) -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return ""
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={key}"
    )
    data = _http_json(
        url,
        {"contents": [{"parts": [{"text": prompt}]}]},
        {"Content-Type": "application/json"},
    )
    parts = data["candidates"][0]["content"]["parts"]
    return "".join(p.get("text") or "" for p in parts)


def _parse_day_json(text: str, day: date) -> dict[str, Any] | None:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        text = m.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None
    kartice = []
    for c in data.get("kartice") or []:
        if not isinstance(c, dict):
            continue
        viri = [v for v in (c.get("viri") or []) if isinstance(v, dict) and str(v.get("url") or "").startswith("http")]
        if not viri:
            continue
        naslov = (c.get("naslov") or "").strip()
        pov = (c.get("povzetek_sl") or "").strip()
        if not naslov or not pov:
            continue
        kartice.append(
            {
                "id": c.get("id") or f"{day.isoformat()}-{_slug(naslov)}",
                "date": day.isoformat(),
                "teme": c.get("teme") or ["ai"],
                "naslov": naslov,
                "povzetek_sl": pov,
                "zakaj_je_vazno": (c.get("zakaj_je_vazno") or "").strip(),
                "status": c.get("status") if c.get("status") in {"paper", "uradno", "govorica", "napoved"} else "govorica",
                "zaupanje": max(1, min(5, int(c.get("zaupanje") or 3))),
                "watch_id": c.get("watch_id") or None,
                "viri": viri,
            }
        )
    return {
        "date": day.isoformat(),
        "naslov_dneva": data.get("naslov_dneva") or f"Radar {day.isoformat()}",
        "recap": None,
        "kartice": kartice[:15],
    }


def synthesize(
    day: date,
    items: list[dict[str, Any]],
    watch_ids: list[str],
) -> dict[str, Any]:
    if not items:
        return {
            "date": day.isoformat(),
            "naslov_dneva": "Tiho — ni virov z URL",
            "recap": None,
            "kartice": [],
        }
    blob = json.dumps(items[:40], ensure_ascii=False, indent=2)[:24000]
    prompt = SYNTH_PROMPT.format(
        watch_ids=", ".join(watch_ids),
        day=day.isoformat(),
        sources=blob,
    )
    text = ""
    try:
        text = _call_xai(prompt)
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, IndexError):
        text = ""
    if not text:
        try:
            text = _call_gemini(prompt)
        except (urllib.error.URLError, urllib.error.HTTPError, KeyError, IndexError):
            text = ""
    if text:
        parsed = _parse_day_json(text, day)
        if parsed and parsed["kartice"]:
            return parsed
    return fallback_cards(day, items)
