"""Step 3 (optional): Wikipedia page text, matched through the Wikidata ID.

Path: Wikidata ID -> English Wikipedia title -> plain-text page.
The "Plot" section is cut out later, in transform.
Run: python -m extract.fetch_wiki_plots
"""
import json
import logging
import time

from extract.common import RAW, get_json, write_raw

log = logging.getLogger("wiki")

# ---- Settings ----
FORCE = False
PAUSE_SECONDS = 0.5   # be polite to Wikimedia, avoids 429s
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"

stats = {"ok": 0, "skipped": 0, "no_wikidata_id": 0, "no_wiki_page": 0}

# ---- Loop over every movie we have details for ----
for details_file in sorted((RAW / "details").glob("*.json")):
    out_file = RAW / "wiki" / details_file.name

    if out_file.exists() and not FORCE:
        stats["skipped"] += 1
        continue

    details = json.loads(details_file.read_text(encoding="utf-8"))
    wikidata_id = details.get("external_ids", {}).get("wikidata_id")
    if not wikidata_id:
        stats["no_wikidata_id"] += 1
        continue

    # 1) Wikidata ID -> English Wikipedia page title
    wd = get_json(WIKIDATA_API, {
        "action": "wbgetentities",
        "ids": wikidata_id,
        "props": "sitelinks",
        "sitefilter": "enwiki",
        "format": "json",
    })
    entity = wd["entities"].get(wikidata_id, {})
    title = entity.get("sitelinks", {}).get("enwiki", {}).get("title")
    if not title:
        stats["no_wiki_page"] += 1
        continue

    # 2) Page title -> full page as plain text
    wp = get_json(WIKIPEDIA_API, {
        "action": "query",
        "prop": "extracts",
        "explaintext": 1,
        "titles": title,
        "redirects": 1,
        "format": "json",
    })
    page = next(iter(wp["query"]["pages"].values()))

    write_raw(out_file, {
        "tmdb_id": details["id"],
        "wikidata_id": wikidata_id,
        "title": title,
        "text": page.get("extract"),
    })
    stats["ok"] += 1
    time.sleep(PAUSE_SECONDS)

    if stats["ok"] % 100 == 0:
        log.info("fetched=%s", stats["ok"])

log.info("done %s", stats)
