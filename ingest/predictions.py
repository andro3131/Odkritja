"""Točkovanje napovedi, tedenski predlogi, nedeljski recap."""

from __future__ import annotations

import json
import os
import re
import urllib.error
from datetime import date, timedelta
from typing import Any

from ingest.config import DNEVI, NAPOVEDI, WATCHLIST
from ingest.synthesize import _call_gemini, _call_xai, _norm_title

PREDLOGI_PROMPT = """Si skepticen urednik. Predlagaj 0 do 3 preverljive napovedi iz spodnjega watchlista in kartic zadnjih 7 dni.
Vsaka mora imeti jasen horizont (datum) in biti ločena od že obstoječih napovedi.
Ne izmišljuj dejstev. Če ni kaj za napovedati, vrni [].

Obstoječe:
{existing}

Watchlist:
{watch}

Kartice (7 dni):
{cards}

SAMO JSON seznam:
[{{"claim": "...", "horizont": "YYYY-MM-DD", "watch_id": "..."}}]
"""


def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def recent_cards(today: date, days: int = 7) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i in range(days):
        p = DNEVI / f"{(today - timedelta(days=i)).isoformat()}.json"
        if p.exists():
            out.extend(json.loads(p.read_text(encoding="utf-8")).get("kartice") or [])
    return out


def score_predictions(today: date) -> list[str]:
    """Zapadle open napovedi: hit če watch_id + uradno v obdobju, sicer zapadlo; po +7 dneh miss."""
    data = load_json(NAPOVEDI, {"posodobljeno": today.isoformat(), "napovedi": []})
    notes: list[str] = []
    cards = recent_cards(today, days=21)
    for n in data.get("napovedi") or []:
        if n.get("status") != "open":
            continue
        try:
            horizont = date.fromisoformat(n["horizont"])
        except (KeyError, ValueError):
            continue
        if horizont > today:
            continue
        wid = n.get("watch_id")
        hits = [
            c
            for c in cards
            if c.get("watch_id") == wid and c.get("status") == "uradno"
        ]
        # Keyword overlap as weak signal
        claim_toks = set(_norm_title(n.get("claim") or "").split())
        if not hits:
            for c in cards:
                t = set(_norm_title(c.get("naslov") or "").split())
                if len(claim_toks & t) >= 3 and c.get("status") in {"uradno", "paper"}:
                    hits.append(c)
                    break
        if hits:
            n["status"] = "hit"
            n["razsodba"] = f"Potrjeno z: {hits[0].get('naslov')}"
            notes.append(f"hit: {n.get('claim')}")
        elif today >= horizont + timedelta(days=7):
            n["status"] = "miss"
            n["razsodba"] = "Horizont + 7 dni, ni uradne potrditve v arhivu."
            notes.append(f"miss: {n.get('claim')}")
        else:
            n["status"] = "zapadlo"
            n["razsodba"] = "Horizont je padel — čaka razsodbo (ročno ali +7 dni → miss)."
            notes.append(f"zapadlo: {n.get('claim')}")
    data["posodobljeno"] = today.isoformat()
    save_json(NAPOVEDI, data)
    return notes


def propose_weekly(today: date) -> list[dict[str, Any]]:
    """Nedelja: 0–3 nove napovedi. Nikoli v dnevne kartice."""
    if today.weekday() != 6 and os.environ.get("FORCE_NAPOVEDI") != "1":
        return []
    data = load_json(NAPOVEDI, {"posodobljeno": today.isoformat(), "napovedi": []})
    existing = [n.get("claim") for n in data.get("napovedi") or [] if n.get("status") in {"open", "zapadlo"}]
    watch = load_json(WATCHLIST, {"teme": []})
    cards = recent_cards(today, 7)
    prompt = PREDLOGI_PROMPT.format(
        existing=json.dumps(existing, ensure_ascii=False),
        watch=json.dumps(
            [{"id": t["id"], "naslov": t["naslov"], "status_sl": t.get("status_sl")} for t in watch.get("teme") or []],
            ensure_ascii=False,
        ),
        cards=json.dumps(
            [{"naslov": c.get("naslov"), "watch_id": c.get("watch_id")} for c in cards[:30]],
            ensure_ascii=False,
        ),
    )
    text = ""
    try:
        text = _call_xai(prompt) or _call_gemini(prompt)
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, IndexError):
        text = ""
    proposed = _parse_list(text)
    added = []
    for p in proposed[:3]:
        claim = (p.get("claim") or "").strip()
        horizont = (p.get("horizont") or "").strip()
        if not claim or not re.match(r"\d{4}-\d{2}-\d{2}$", horizont):
            continue
        if any(_norm_title(claim) == _norm_title(x or "") for x in existing):
            continue
        item = {
            "id": f"p-{today.isoformat()}-{len(data['napovedi']) + 1}",
            "claim": claim,
            "narejena": today.isoformat(),
            "horizont": horizont,
            "status": "open",
            "watch_id": p.get("watch_id") or None,
            "razsodba": None,
        }
        data["napovedi"].append(item)
        added.append(item)
        existing.append(claim)
    if added:
        data["posodobljeno"] = today.isoformat()
        save_json(NAPOVEDI, data)
    return added


def sunday_recap(today: date) -> str | None:
    if today.weekday() != 6 and os.environ.get("FORCE_RECAP") != "1":
        return None
    watch = load_json(WATCHLIST, {"teme": []})
    lines = ["Tedenski recap watchlista:"]
    week_ago = (today - timedelta(days=7)).isoformat()
    moved = False
    for t in watch.get("teme") or []:
        zg = [z for z in (t.get("zgodovina") or []) if (z.get("date") or "") >= week_ago]
        if zg:
            moved = True
            lines.append(f"— {t.get('naslov')}: {zg[-1].get('text')}")
    data = load_json(NAPOVEDI, {"napovedi": []})
    due = [n for n in data.get("napovedi") or [] if n.get("horizont") and n["horizont"] <= today.isoformat() and n.get("status") in {"open", "zapadlo"}]
    if due:
        moved = True
        lines.append("Zapadle napovedi: " + "; ".join(n.get("claim", "")[:80] for n in due))
    if not moved:
        lines.append("Ni premikov na watchlistu. To je tudi podatek.")
    return "\n".join(lines)


def update_watchlist(today: date, kartice: list[dict[str, Any]]) -> None:
    data = load_json(WATCHLIST, {"posodobljeno": today.isoformat(), "teme": []})
    by_id = {t["id"]: t for t in data.get("teme") or [] if t.get("id")}
    for c in kartice:
        wid = c.get("watch_id")
        if not wid or wid not in by_id:
            continue
        t = by_id[wid]
        text = c.get("naslov") or ""
        zg = t.setdefault("zgodovina", [])
        if any(z.get("text") == text and z.get("date") == today.isoformat() for z in zg):
            continue
        zg.append({"date": today.isoformat(), "text": text})
        t["zadnja_sprememba"] = today.isoformat()
    data["posodobljeno"] = today.isoformat()
    data["teme"] = list(by_id.values())
    save_json(WATCHLIST, data)


def _parse_list(text: str) -> list[dict[str, Any]]:
    if not text:
        return []
    text = text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        text = m.group(1).strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
    except json.JSONDecodeError:
        m = re.search(r"\[[\s\S]*\]", text)
        if m:
            try:
                data = json.loads(m.group(0))
                if isinstance(data, list):
                    return [x for x in data if isinstance(x, dict)]
            except json.JSONDecodeError:
                return []
    return []
