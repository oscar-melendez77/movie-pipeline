"""Move the data between your machine / GitHub Actions and Hugging Face.

Hugging Face holds 3 files in a "dataset" repo (free storage):
  raw.tar.gz      - every raw JSON file, packed into one archive
  movies.duckdb   - the database (raw tables, dbt models, chunks + vectors)
  known_ids.json  - IDs of every movie we have (for the daily check)

Run:
  python scripts/hf_sync.py download   -> get the latest data from Hugging Face
  python scripts/hf_sync.py upload     -> send your data to Hugging Face

Needs in .env (or GitHub secrets/variables):
  HF_TOKEN         - Hugging Face token with WRITE access
  HF_DATASET_REPO  - e.g. your-username/movie-pipeline-data
"""
import json
import os
import sys
import tarfile
from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import HfApi, hf_hub_download

# ---- Settings ----
load_dotenv()
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ARCHIVE = DATA / "raw.tar.gz"
DB_FILE = DATA / "movies.duckdb"

TOKEN = os.getenv("HF_TOKEN")
DATASET_REPO = os.getenv("HF_DATASET_REPO")

if not TOKEN or not DATASET_REPO:
    raise SystemExit("Set HF_TOKEN and HF_DATASET_REPO first (in .env)")

api = HfApi(token=TOKEN)
action = sys.argv[1] if len(sys.argv) > 1 else ""

# ---- DOWNLOAD: Hugging Face -> data/ ----
if action == "download":
    for name in ["raw.tar.gz", "movies.duckdb"]:
        hf_hub_download(DATASET_REPO, name, repo_type="dataset",
                        local_dir=DATA, token=TOKEN)
        print(f"downloaded {name}")

    # Unpack raw.tar.gz back into data/raw/
    with tarfile.open(ARCHIVE) as tar:
        tar.extractall(DATA, filter="data")
    print("unpacked data/raw/")

# ---- UPLOAD: data/ -> Hugging Face, then refresh the app ----
elif action == "upload":
    # 1) Pack data/raw/ into one archive (thousands of small files -> 1 file)
    with tarfile.open(ARCHIVE, "w:gz") as tar:
        tar.add(DATA / "raw", arcname="raw")
    print(f"packed raw -> {ARCHIVE.name} ({ARCHIVE.stat().st_size / 1e6:.0f} MB)")

    # 2) Save the list of movie IDs we have (used by the daily check)
    known_ids = sorted(int(p.stem) for p in (DATA / "raw" / "details").glob("*.json"))
    KNOWN_IDS = DATA / "known_ids.json"
    KNOWN_IDS.write_text(json.dumps(known_ids))
    print(f"saved known_ids.json ({len(known_ids)} movies)")

    # 3) Upload the files to the dataset repo (created the first time)
    api.create_repo(DATASET_REPO, repo_type="dataset", private=False, exist_ok=True)
    for path in [ARCHIVE, DB_FILE, KNOWN_IDS]:
        api.upload_file(path_or_fileobj=path, path_in_repo=path.name,
                        repo_id=DATASET_REPO, repo_type="dataset")
        print(f"uploaded {path.name}")

    # The Streamlit app picks up the new movies.duckdb by itself (checks daily)

else:
    raise SystemExit("Use: python scripts/hf_sync.py download | upload")
