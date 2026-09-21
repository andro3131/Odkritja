# Odkritja — pravila

Osebni dnevni radar (medicina, AI, SpaceX, Tesla, robotika, fizika).
**Ni news feed.** 8–15 kartic na dan, vir obvezen, watchlist živi tedne.

## Česa ne delamo

- Scrapanje x.com / Selenium / neuradni Twitter API
- X API pay-per-use kot primarni vir
- Kartica brez URL
- Povzemanje v dva stavka
- Mešanje napovedi z novicami
- Kindle mail, dokler user ne prosi

## X

X Premium ≠ developer API. Kanal je uradni **xAI `x_search`** (`XAI_API_KEY`).
Brez ključa: RSS + `content/inbox.md`.

## Dnevni zagon

```bash
cd Odkritja
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # vstavi ključ
python ingest.py
```

Odpri `index.html` (lokalno ali Vercel). GitHub Action: `.github/workflows/daily.yml` ob 07:00 CET.

Strop: `DAILY_COST_CAP` (privzeto 0,15 $/dan). Poraba: `content/usage.json`.

## Datoteke

| Pot | Kaj |
|-----|-----|
| `content/dnevi/YYYY-MM-DD.json` | brief dneva |
| `content/watchlist.json` | žive teme |
| `content/napovedi.json` | napovedi, točkovanje |
| `content/inbox.md` | prilepek URL |
| `content/usage.json` | stroški x_search |

## Jezik kartic

Živa slovenščina, ~1 EN beseda na stavek poleg imen (FSD, Starship, feed, paper).
Sintaza sme **samo** preoblikovati vire — ne izmišljevati datumov poletov ali imen zdravil.
