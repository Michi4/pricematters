"""Cache warmer: pre-fill popular + staple queries so clicks never burn provider budget.

Called post-deploy by CI (.github/workflows/deploy.yml) and every 6h via cron:
  17 */6 * * * cd /home/ubuntu/websters/customers/pricematters && \
    docker compose exec -T backend python warm.py >> /tmp/pm-warm.log 2>&1
"""
import json
import os
import urllib.parse
import urllib.request

BASE = os.getenv("WARM_BASE", "http://localhost:8000")
DEFAULTS = ["Reis", "Kaffee", "Protein", "Erdnussmus", "Olivenöl", "Haferflocken"]


def get(path: str):
    with urllib.request.urlopen(BASE + path, timeout=150) as r:
        return json.loads(r.read().decode())


def main():
    try:
        popular = get("/popular?marketplace=de").get("items", [])
    except Exception as e:
        print("popular failed:", e)
        popular = []

    for q in list(dict.fromkeys(popular + DEFAULTS))[:12]:
        for mp in ("de", "com"):
            try:
                d = get("/search?" + urllib.parse.urlencode({"q": q, "marketplace": mp}))
                print(f"{mp} {q}: {len(d.get('items', []))} via {d.get('meta', {}).get('provider_used')}",
                      flush=True)
            except Exception as e:
                print(f"{mp} {q}: FAIL {e}", flush=True)


if __name__ == "__main__":
    main()
