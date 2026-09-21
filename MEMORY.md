# Vremenko · MEMORY

> Handoff. Zadnja posodobitev: **2026-09-09**.

## Kaj je

Statični HTML + JSON (kot Kavarna Škocjan). Python ingest zjutraj.
Štiri strani: Danes, Spremljam, Napovedi, Arhiv.

## Odločitve

- **Ne scrapaj X.** xAI `x_search` ali inbox prilepek.
- Model za ingest: `grok-4.3` (cenejši), ne 4.6.
- Od 21. 9. 2026 je x_search 5 $/1000 **tvitov** — ena poizvedba na dan, max 20 handle, `from_date` = včeraj, cap 0,15 $.
- Watchlist je produkt, ne firehose.
- Napovedi nikoli v istem nizu kot novice (razen nedeljskega recap bloka).

## Watchlist (začetni)

`fsd-slovenia`, `starship-next`, `gpt6-astra`, `alphagenome-atlas`, `navier-stokes`, `rentosertib`, `semaglutid`.

## Ključi

`XAI_API_KEY` (idealno) ali `GEMINI_API_KEY` (samo RSS). Cursor chat **ni** cron.
GitHub secrets z istimi imeni za Action.

## Cron

- GitHub Action `daily.yml` — 05:00 UTC = 07:00 CEST
- Fallback: `macos/com.odkritja.ingest.plist` (label `com.vremenko.ingest`) → `launchctl load`

## Odprto

- Vercel projekt + GitHub remote (prvi push)
- API ključ v `.env` / GitHub secret
- Deployment Protection, če nočeš javnega URL
