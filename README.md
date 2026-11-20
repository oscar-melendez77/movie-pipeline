# movie-pipeline

Describe a movie, get the most likely matches.

## Setup
```
python -m venv .venv
.venv\Scripts\activate        # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env        # then paste your TMDB key
```

## Extract (run from the project root, in order)
```
python -m extract.fetch_discover      # edit settings at top of each file
python -m extract.fetch_details
python -m extract.fetch_wiki_plots     # optional
```

## Layout
```
extract/    API -> data/raw (done)
load/       raw -> DuckDB (next)
transform/  clean + plot text
search/     embeddings + query
data/raw/   discover/year=YYYY/page_N.json, details/{id}.json, wiki/{id}.json
```
