"""Shared setup used by the three ingestion scripts.

Holds the settings (paths, API key) and 4 small helpers:
  get_json   - GET a URL, retry if rate-limited or the server fails
  tmdb       - shortcut for calling TMDB with your API key
  write_raw  - save JSON to disk safely
  movie_ids  - list every movie ID found in the discover pages
"""
import json
import logging
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

# ---- Settings ----
load_dotenv()                                   # reads TMDB_API_KEY from .env
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE = "https://api.themoviedb.org/3"

# Wikipedia blocks requests without contact info in the User-Agent
USER_AGENT = "movie-pipeline/0.1 (https://linkedin.com/in/josueme91)"

ROOT = Path(__file__).resolve().parent.parent   # project folder
RAW = ROOT / "data" / "raw"                     # where raw JSON lands

MAX_RETRIES = 3
WAIT_SECONDS = 2.0                              # grows with each retry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
log = logging.getLogger("http")


def get_json(url, params=None):
    """GET a URL and return its JSON. Retries on 429 / 5xx / network errors."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, params=params, timeout=20,
                                    headers={"User-Agent": USER_AGENT})
        except requests.RequestException as error:
            # Network problem (timeout, no connection...)
            if attempt == MAX_RETRIES:
                raise
            log.warning("error=%s attempt=%s", error, attempt)
            time.sleep(WAIT_SECONDS * attempt)
            continue

        # 429 = too many requests, 5xx = server problem -> wait and retry
        if response.status_code == 429 or response.status_code >= 500:
            wait = float(response.headers.get("Retry-After", WAIT_SECONDS * attempt))
            log.warning("status=%s attempt=%s wait=%.1fs", response.status_code, attempt, wait)
            time.sleep(wait)
            continue

        response.raise_for_status()   # any other error (401, 404...) -> fail loudly
        return response.json()

    raise RuntimeError(f"Gave up after {MAX_RETRIES} attempts: {url}")


def tmdb(path, **params):
    """Call a TMDB endpoint, e.g. tmdb("/movie/550")."""
    if not TMDB_API_KEY:
        raise RuntimeError("TMDB_API_KEY missing - put it in .env")
    params["api_key"] = TMDB_API_KEY
    return get_json(TMDB_BASE + path, params)


def write_raw(path, data):
    """Save JSON. Writes a .tmp file first, then renames it, so a crash
    mid-write never leaves a half-written file behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(path)


def movie_ids():
    """Every unique movie ID across all landed discover pages."""
    ids = set()
    for page_file in (RAW / "discover").rglob("page_*.json"):
        page = json.loads(page_file.read_text(encoding="utf-8"))
        for movie in page["results"]:
            ids.add(movie["id"])
    return sorted(ids)
