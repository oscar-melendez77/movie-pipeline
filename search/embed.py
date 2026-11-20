"""Step 4a: split every movie's text into chunks and embed each chunk.

Reads:  movies (built by dbt)
Writes: movie_chunks - 1 row per chunk: movie_id, chunk_no, chunk_text, embedding

Incremental: a movie is only (re)embedded if it's new or its text changed.
We detect changes with a hash (fingerprint) of search_text.

Run: python -m search.embed
"""
from pathlib import Path

import duckdb
from sentence_transformers import SentenceTransformer

# ---- Settings ----
ROOT = Path(__file__).resolve().parent.parent
DB_FILE = ROOT / "data" / "movies.duckdb"

MODEL_NAME = "BAAI/bge-small-en-v1.5"
VECTOR_SIZE = 384        # this model outputs 384 numbers per text
CHUNK_WORDS = 150        # ~200 tokens; small chunks keep each scene specific
OVERLAP_WORDS = 30       # words repeated between chunks so no sentence is cut off
BATCH_SIZE = 64          # chunks embedded at once

con = duckdb.connect(str(DB_FILE))

# ---- 1) Make sure the chunks table exists ----
con.execute(f"""
    CREATE TABLE IF NOT EXISTS movie_chunks (
        movie_id    INTEGER,
        chunk_no    INTEGER,
        chunk_text  VARCHAR,
        text_hash   VARCHAR,          -- fingerprint of the movie's full text
        model       VARCHAR,          -- which model made the vector
        embedding   FLOAT[{VECTOR_SIZE}]
    )
""")

# ---- 2) Remove chunks that are out of date ----
# a) movies that disappeared from the movies table
# b) movies whose text changed, or that were embedded with another model
con.execute("""
    DELETE FROM movie_chunks c
    WHERE NOT EXISTS (
        SELECT 1 FROM movies m
        WHERE m.id = c.movie_id
          AND md5(m.search_text) = c.text_hash
          AND c.model = ?
    )
""", [MODEL_NAME])

# ---- 3) Find movies that still need embedding ----
todo = con.execute("""
    SELECT id, search_text, md5(search_text) AS text_hash
    FROM movies
    WHERE id NOT IN (SELECT DISTINCT movie_id FROM movie_chunks)
""").fetchall()
print(f"movies to embed: {len(todo)}")

if not todo:
    print("nothing to do")
    con.close()
    raise SystemExit

# ---- 4) Split each movie's text into overlapping chunks ----
#   words 0-149 -> chunk 0, words 120-269 -> chunk 1, ... (30 words overlap)
step = CHUNK_WORDS - OVERLAP_WORDS
chunks = []   # (movie_id, chunk_no, chunk_text, text_hash)

for movie_id, text, text_hash in todo:
    words = text.split()
    chunk_no = 0
    for start in range(0, len(words), step):
        piece = " ".join(words[start:start + CHUNK_WORDS])
        chunks.append((movie_id, chunk_no, piece, text_hash))
        chunk_no += 1
        if start + CHUNK_WORDS >= len(words):   # last chunk reached the end
            break

print(f"chunks to embed: {len(chunks)}")

# ---- 5) Embed all chunks ----
# First run downloads the model (~90 MB) into your user cache.
# normalize_embeddings=True makes cosine similarity a simple, fair comparison.
model = SentenceTransformer(MODEL_NAME)
texts = [c[2] for c in chunks]
vectors = model.encode(
    texts,
    batch_size=BATCH_SIZE,
    normalize_embeddings=True,
    show_progress_bar=True,
)

# ---- 6) Save chunks + vectors ----
rows = []
for (movie_id, chunk_no, piece, text_hash), vector in zip(chunks, vectors):
    rows.append([movie_id, chunk_no, piece, text_hash, MODEL_NAME, vector.tolist()])

con.executemany("INSERT INTO movie_chunks VALUES (?, ?, ?, ?, ?, ?)", rows)

total = con.execute("SELECT COUNT(*), COUNT(DISTINCT movie_id) FROM movie_chunks").fetchone()
print(f"movie_chunks now has {total[0]} chunks for {total[1]} movies")
con.close()
