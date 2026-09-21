# Vremenko

Osebni dnevni radar: medicina, AI, SpaceX, Tesla. Statična stran + Python ingest.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python ingest.py          # RSS + inbox; x_search če je XAI_API_KEY
python ingest.py --no-x   # brez X
python ingest.py --dry    # ne piši datotek
```

Lokalno: odpri `index.html` ali `python3 -m http.server 8766`.

Prilepek tvitov/člankov: `content/inbox.md` (en URL na vrstico).
