"""Step 4b: describe a movie, get the most likely matches.

Embeds your description, compares it with every chunk of every movie,
and scores each movie by the average of its 3 best-matching chunks.

Run: python -m search.find "a boy discovers he is a wizard"
 or: python -m search.find          (then type descriptions; empty line quits)
"""
import sys
from pathlib import Path

import duckdb
from sentence_transformers import SentenceTransformer

# ---- Settings ----
ROOT = Path(__file__).resolve().parent.parent
DB_FILE = ROOT / "data" / "movies.duckdb"
MODEL_NAME = "BAAI/bge-small-en-v1.5"   # must match embed.py
VECTOR_SIZE = 384
TOP_N = 10
CHUNKS_PER_MOVIE = 3     # a movie's score = average of its 3 best chunks

# BGE models expect this prefix on the QUESTION (not on the movie chunks)
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

con = duckdb.connect(str(DB_FILE), read_only=True)
model = SentenceTransformer(MODEL_NAME)

# Description from the command line, or ask for it
if len(sys.argv) > 1:
    descriptions = [" ".join(sys.argv[1:])]
else:
    descriptions = iter(lambda: input("\nDescribe a movie (empty = quit): ").strip(), "")

for description in descriptions:

    # 1) Turn the description into a vector, the same way the chunks were
    query_vector = model.encode(QUERY_PREFIX + description, normalize_embeddings=True).tolist()

    # 2) Similarity with every chunk
    #    -> keep each movie's 3 best chunks
    #    -> movie score = their average (one lucky chunk can't win alone)
    #    cosine similarity: 1.0 = same meaning, 0 = unrelated
    results = con.execute(f"""
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
            avg(r.similarity)                    AS score,
            arg_max(r.chunk_text, r.similarity)  AS best_chunk
        FROM ranked r
        JOIN movies m ON m.id = r.movie_id
        WHERE r.chunk_rank <= {CHUNKS_PER_MOVIE}
        GROUP BY m.title, m.year
        ORDER BY score DESC
        LIMIT {TOP_N}
    """, [query_vector]).fetchall()

    # 3) Print
    print(f'\nTop {TOP_N} for: "{description}"\n')
    for rank, (title, year, score, best_chunk) in enumerate(results, start=1):
        print(f"{rank:>2}. {title} ({year})  score={score:.3f}")
        print(f"    ...{best_chunk[:140]}...")

con.close()
