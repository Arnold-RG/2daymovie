from data.demo_movies import DEMO_MOVIES
from services.tmdb import poster_url, backdrop_url
import requests

for m in DEMO_MOVIES:
    title = m["title"]
    checks = [
        ("poster", poster_url(m.get("poster_path"))),
        ("backdrop", backdrop_url(m.get("backdrop_path"))),
    ]
    for label, url in checks:
        if not url:
            print(f"MISSING {label}: {title}")
            continue
        try:
            r = requests.get(url, timeout=15, stream=True)
            print(f"{r.status_code} {label:8} {title}")
            r.close()
        except Exception as e:
            print(f"ERR {label} {title}: {e}")
