"""Step 5: web app. Describe a movie, get the most likely matches.

Run locally:  streamlit run app/streamlit_app.py
Online:       Streamlit Community Cloud runs this same file from GitHub.

Locally it reads data/movies.duckdb. Online there is no local file,
so it downloads movies.duckdb from your Hugging Face dataset.
"""
import os
from pathlib import Path

import duckdb
import streamlit as st
from huggingface_hub import hf_hub_download
from sentence_transformers import SentenceTransformer

# ---- Settings ----
ROOT = Path(__file__).resolve().parent.parent
LOCAL_DB = ROOT / "data" / "movies.duckdb"
# Online, set HF_DATASET_REPO in the app's Secrets (Streamlit Cloud settings)
try:
    HF_DATASET_REPO = st.secrets["HF_DATASET_REPO"]
except Exception:
    HF_DATASET_REPO = os.getenv("HF_DATASET_REPO", "")   # no secrets file locally
MODEL_NAME = "BAAI/bge-small-en-v1.5"      # must match search/embed.py
VECTOR_SIZE = 384
TOP_N = 10
CHUNKS_PER_MOVIE = 3
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


# ---- Load the model once for everyone (cached) ----
@st.cache_resource
def load_model():
    return SentenceTransformer(MODEL_NAME)


# ---- Load the database (cached, re-checked once a day) ----
# hf_hub_download only re-downloads if the weekly job uploaded a new file
@st.cache_resource(ttl=60 * 60 * 24)
def load_database():
    if LOCAL_DB.exists():
        db_path = LOCAL_DB
    else:
        db_path = hf_hub_download(HF_DATASET_REPO, "movies.duckdb", repo_type="dataset")
    return duckdb.connect(str(db_path), read_only=True)


SEARCH_SQL = f"""
    WITH scored AS (
        SELECT
            movie_id,
            chunk_text,
            array_cosine_similarity(embedding, ?::FLOAT[{VECTOR_SIZE}]) AS similarity
        FROM movie_chunks
    ),
    ranked AS (
        SELECT
            *,
            row_number() OVER (PARTITION BY movie_id ORDER BY similarity DESC) AS chunk_rank
        FROM scored
    )
    SELECT
        m.title,
        m.year,
        array_to_string(m.genres, ', ')      AS genres,
        avg(r.similarity)                    AS score,
        arg_max(r.chunk_text, r.similarity)  AS best_chunk
    FROM ranked r
    JOIN movies m ON m.id = r.movie_id
    WHERE r.chunk_rank <= {CHUNKS_PER_MOVIE}
    GROUP BY m.title, m.year, m.genres
    ORDER BY score DESC
    LIMIT {TOP_N}
"""

# ---- The page (Streamlit runs this top to bottom on every interaction) ----
st.set_page_config(page_title="Find that movie", page_icon="🎬")
st.title("🎬 Find that movie")
st.write("Describe a plot in your own words.")

with st.spinner("Loading model and database (first visit takes ~1 minute)..."):
    model = load_model()
    con = load_database()

description = st.text_area(
    "Describe the movie",
    placeholder="e.g. a boy discovers he is a wizard and goes to a magic school",
)

if st.button("Search", type="primary") and description.strip():
    query_vector = model.encode(QUERY_PREFIX + description, normalize_embeddings=True).tolist()
    results = con.execute(SEARCH_SQL, [query_vector]).fetchall()

    for rank, (title, year, genres, score, best_chunk) in enumerate(results, start=1):
        st.subheader(f"{rank}. {title} ({year})")
        st.caption(f"Match: {score:.0%} · Genres: {genres}")
        st.markdown(f"> ...{best_chunk[:250]}...")
