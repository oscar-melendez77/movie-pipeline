"""Step 1: land /discover/movie pages, one folder per release year.

Run: python -m extract.fetch_discover
"""
import logging
import os

from extract.common import RAW, tmdb, write_raw

log = logging.getLogger("discover")

# ---- Settings ----
# Defaults for a full pull. The weekly GitHub Action overrides them
# with environment variables to fetch only the current year.
START_YEAR = int(os.getenv("START_YEAR", 2000))
END_YEAR = int(os.getenv("END_YEAR", 2025))
PAGES_PER_YEAR = 5   # 20 movies per page

# ---- Fetch every page for every year ----
for year in range(START_YEAR, END_YEAR + 1):
    for page in range(1, PAGES_PER_YEAR + 1):

        data = tmdb(
            "/discover/movie",
            primary_release_year=year,
            sort_by="vote_count.desc",
            page=page,
            language="en-US",
        )

        # Same path on every run -> re-running overwrites, never duplicates
        out_file = RAW / "discover" / f"year={year}" / f"page_{page}.json"
        write_raw(out_file, data)
        log.info("year=%s page=%s results=%s", year, page, len(data["results"]))

        # Stop early if the year has fewer pages than we asked for
        if page >= data.get("total_pages", 0):
            break
