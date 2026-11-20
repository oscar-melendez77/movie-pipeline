"""Step 2: per-movie keywords + Wikidata ID (one request per movie).

Skips movies already landed. Set FORCE = True to refetch everything.
Run: python -m extract.fetch_details
"""
import logging

from extract.common import RAW, movie_ids, tmdb, write_raw

log = logging.getLogger("details")

# ---- Settings ----
FORCE = False

# ---- Fetch details for every movie found in the discover pages ----
ids = movie_ids()
fetched = 0
skipped = 0

for movie_id in ids:
    out_file = RAW / "details" / f"{movie_id}.json"

    # Incremental: don't refetch what we already have
    if out_file.exists() and not FORCE:
        skipped += 1
        continue

    # append_to_response bundles keywords + external IDs into this one call
    data = tmdb(f"/movie/{movie_id}", append_to_response="keywords,external_ids")
    write_raw(out_file, data)
    fetched += 1

    if fetched % 100 == 0:
        log.info("fetched=%s / %s", fetched, len(ids))

log.info("total=%s fetched=%s skipped=%s", len(ids), fetched, skipped)
