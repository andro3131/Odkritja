"""Ena dnevna xAI x_search poizvedba. Ni scrapanje x.com."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import date, timedelta
from typing import Any

from ingest.config import estimate_x_search_usd, handles_for_weekday


PROMPT = """Išči samo zadnje resne novice/odkritja (zadnjih ~36 ur) z dovoljenih X računov.

Vrni SAMO JSON seznam, max 12 objektov:
[{{"naslov": "...", "povzetek": "2-4 stavki EN ali SL", "url": "https://x.com/...", "handle": "...", "teme": ["ai"|"medicina"|"spacex"|"tesla"|"robotika"|"fizika"]}}]

Samo stvari z javnim URL tvita. Brez memes, brez ponavljanja iste novice. Če ni nič resnega, vrni [].
Teme danes: {focus}.
"""


def _focus(weekday: int) -> str:
    if weekday in (0, 2, 4):
        return "SpaceX, Starship, Tesla, FSD"
    if weekday in (1, 3, 5):
        return "AI modeli, medicina, papirji, robotika"
    return "mix: SpaceX/Tesla + AI/medicina"


def fetch_x_search(
    today: date,
    cap_usd: float,
    already_spent: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Vrni (zadetki, usage_meta).
    Če ni ključa ali cap, prazno + razlog.
    """
    key = os.environ.get("XAI_API_KEY", "").strip()
    meta: dict[str, Any] = {
        "skipped": False,
        "reason": None,
        "calls": 0,
        "posts_est": 0,
        "estimated_usd": 0.0,
        "handles": [],
    }
    if not key:
        meta["skipped"] = True
        meta["reason"] = "ni XAI_API_KEY"
        return [], meta

    yesterday = today - timedelta(days=1)
    handles = handles_for_weekday(today.weekday())
    posts_est = 20
    cost = estimate_x_search_usd(today, posts_est, calls=1)
    if already_spent + cost > cap_usd:
        meta["skipped"] = True
        meta["reason"] = f"cost cap {cap_usd} (ocena {cost:.3f})"
        meta["handles"] = handles
        return [], meta

    model = os.environ.get("XAI_MODEL", "grok-4.3")
    body = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": PROMPT.format(focus=_focus(today.weekday())),
            }
        ],
        "tools": [
            {
                "type": "x_search",
                "allowed_x_handles": handles,
                "from_date": yesterday.isoformat(),
                "to_date": today.isoformat(),
            }
        ],
    }
    req = urllib.request.Request(
        "https://api.x.ai/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="ignore")[:400]
        meta["skipped"] = True
        meta["reason"] = f"HTTP {e.code}: {err}"
        return [], meta
    except Exception as e:
        meta["skipped"] = True
        meta["reason"] = str(e)
        return [], meta

    text = _extract_text(payload)
    items = _parse_json_list(text)
    posts = _count_posts(payload) or max(len(items), 1)
    actual = estimate_x_search_usd(today, posts, calls=1)
    meta.update(
        {
            "calls": 1,
            "posts_est": posts,
            "estimated_usd": round(actual, 4),
            "handles": handles,
            "model": model,
        }
    )
    out = []
    for it in items[:12]:
        url = (it.get("url") or "").strip()
        if not url.startswith("http"):
            continue
        out.append(
            {
                "id": f"x-{url}",
                "tip": "x",
                "naslov": (it.get("naslov") or "").strip(),
                "povzetek": (it.get("povzetek") or "").strip(),
                "url": url,
                "handle": (it.get("handle") or "").lstrip("@"),
                "teme": it.get("teme") or ["ai"],
            }
        )
    return out, meta


def _extract_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    chunks: list[str] = []
    for item in payload.get("output") or payload.get("choices") or []:
        if isinstance(item, dict):
            if item.get("type") == "message":
                for c in item.get("content") or []:
                    if isinstance(c, dict) and c.get("text"):
                        chunks.append(c["text"])
            msg = item.get("message") or {}
            if isinstance(msg, dict) and msg.get("content"):
                chunks.append(str(msg["content"]))
    if payload.get("choices"):
        ch0 = payload["choices"][0]
        chunks.append(str(ch0.get("message", {}).get("content") or ch0.get("text") or ""))
    return "\n".join(chunks)


def _count_posts(payload: dict[str, Any]) -> int:
    n = 0
    blob = json.dumps(payload)
    n += blob.lower().count('"type": "x_search"')
    citations = payload.get("citations") or []
    if isinstance(citations, list) and citations:
        return max(len(citations), n)
    return 0


def _parse_json_list(text: str) -> list[dict[str, Any]]:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        text = m.group(1).strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return [x for x in data["items"] if isinstance(x, dict)]
    except json.JSONDecodeError:
        pass
    m = re.search(r"\[[\s\S]*\]", text)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, list):
                return [x for x in data if isinstance(x, dict)]
        except json.JSONDecodeError:
            return []
    return []
