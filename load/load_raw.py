"""Step 2: load the raw JSON files into DuckDB, unchanged.

Creates data/movies.duckdb with 3 tables:
  raw_discover - 1 row per movie per discover page
  raw_details  - 1 row per movie, full JSON kept in a "data" column
  raw_wiki     - 1 row per movie that has a Wikipedia page

Every run rebuilds the tables from scratch (CREATE OR REPLACE),
so running it twice never duplicates rows.

Run: python -m load.load_raw
"""
from pathlib import Path

import duckdb

# ---- Settings ----
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
DB_FILE = ROOT / "data" / "movies.duckdb"

# DuckDB wants forward slashes, even on Windows
discover_files = (RAW / "discover" / "*" / "page_*.json").as_posix()
details_files = (RAW / "details" / "*.json").as_posix()
wiki_files = (RAW / "wiki" / "*.json").as_posix()

# ---- Connect (creates the file if it doesn't exist) ----
con = duckdb.connect(str(DB_FILE))

# ---- 1) Discover pages -> one row per movie ----
# hive_partitioning turns the "year=2015" folder into a "year" column
# unnest(results) explodes each page's 20 movies into 20 rows
con.execute(f"""
    CREATE OR REPLACE TABLE raw_discover AS
    SELECT
        unnest(results, recursive := true),
        year,
        page,
        filename          AS source_file,
        current_timestamp AS loaded_at
    FROM read_json_auto('{discover_files}',
                        filename = true,
                        hive_partitioning = true)
""")

# ---- 2) Movie details -> one row per movie ----
# Each file is stored whole in a JSON column called "data".
# (Letting DuckDB guess columns for 2,600 nested files runs out of memory;
#  we pick the fields we need later, in transform.)
con.execute(f"""
    CREATE OR REPLACE TABLE raw_details AS
    SELECT
        CAST(content::JSON ->> 'id' AS INTEGER) AS id,
        content::JSON                           AS data,
        filename                                AS source_file,
        current_timestamp                       AS loaded_at
    FROM read_text('{details_files}')
""")

# ---- 3) Wikipedia pages -> one row per movie ----
# Same idea: keep the whole file, pull out the ID and the page text
con.execute(f"""
    CREATE OR REPLACE TABLE raw_wiki AS
    SELECT
        CAST(content::JSON ->> 'tmdb_id' AS INTEGER) AS tmdb_id,
        content::JSON ->> 'title'                    AS wiki_title,
        content::JSON ->> 'text'                     AS wiki_text,
        filename                                     AS source_file,
        current_timestamp                            AS loaded_at
    FROM read_text('{wiki_files}')
""")

# ---- Report row counts ----
for table in ["raw_discover", "raw_details", "raw_wiki"]:
    rows = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"{table:<14} {rows:>6} rows")

unique_movies = con.execute("SELECT COUNT(DISTINCT id) FROM raw_details").fetchone()[0]
print(f"unique movies in details: {unique_movies}")

con.close()
