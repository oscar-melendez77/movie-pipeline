"""Daily check: are there new movies this year that we don't have yet?

Cheap on purpose: 5 TMDB calls + 1 tiny file download. No database, no model.
If something is new, it tells GitHub Actions to run the full refresh.

How it knows what we have: every upload saves known_ids.json (the list of
movie IDs we already fetched) to the Hugging Face dataset.

Run: python -m scripts.check_new_movies
"""
import json
import os
from datetime import date

from huggingface_hub import hf_hub_download
from huggingface_hub.errors import EntryNotFoundError

from extract.common import tmdb

# ---- Settings (must match extract/fetch_discover.py) ----
YEAR = date.today().year
PAGES = 5
DATASET_REPO = os.environ["HF_DATASET_REPO"]

# ---- 1) What we already have ----
try:
    path = hf_hub_download(DATASET_REPO, "known_ids.json", repo_type="dataset",
                           token=os.getenv("HF_TOKEN"))
    with open(path) as f:
        known_ids = set(json.load(f))
except EntryNotFoundError:
    known_ids = set()          # first run: no list yet -> treat everything as new

# ---- 2) What TMDB lists right now for this year ----
current_ids = set()
for page in range(1, PAGES + 1):
    data = tmdb("/discover/movie", primary_release_year=YEAR,
                sort_by="vote_count.desc", page=page, language="en-US")
    current_ids.update(movie["id"] for movie in data["results"])
    if page >= data.get("total_pages", 0):
        break

# ---- 3) Compare ----
new_ids = current_ids - known_ids
print(f"year={YEAR} listed={len(current_ids)} known={len(known_ids)} new={len(new_ids)}")

# ---- 4) Tell GitHub Actions (it reads this file to decide the next job) ----
has_new = "true" if new_ids else "false"
github_output = os.getenv("GITHUB_OUTPUT")
if github_output:
    with open(github_output, "a") as f:
        f.write(f"has_new={has_new}\n")
print(f"has_new={has_new}")
