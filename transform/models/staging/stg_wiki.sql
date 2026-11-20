-- One row per movie: cut the plot section out of the full Wikipedia page.
-- Pages mark sections like "== Plot ==". Some use "Synopsis" or "Premise".
-- (?s) lets "." cross line breaks; the plot ends at the next "== Heading ==".

with plots as (
    select
        tmdb_id as id,
        wiki_title,
        regexp_extract(
            wiki_text,
            '(?s)==\s*(?:Plot|Plot summary|Synopsis|Premise)\s*==\s*\n(.*?)(?:\n==[^=]|$)',
            1
        ) as plot
    from {{ source('raw', 'raw_wiki') }}
)

select
    id,
    wiki_title,
    nullif(trim(plot), '') as wiki_plot
from plots
