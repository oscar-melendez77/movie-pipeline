-- Final table: one row per movie, ready to be embedded and searched

with details as (
    select * from {{ ref('stg_details') }}
),

wiki as (
    select * from {{ ref('stg_wiki') }}
),

joined as (
    select
        d.id,
        d.title,
        d.year,
        d.release_date,
        d.genres,
        d.keywords,
        d.overview,
        w.wiki_plot,
        d.vote_average,
        d.vote_count,
        d.popularity
    from details d
    left join wiki w on w.id = d.id      -- keep movies without a wiki page
)

select
    *,
    -- The text we will embed: best plot available + keywords
    concat_ws(
        E'\n\n',
        coalesce(wiki_plot, overview),
        'Keywords: ' || array_to_string(keywords, ', ')
    ) as search_text,
    wiki_plot is not null as has_wiki_plot
from joined
where overview is not null or wiki_plot is not null    -- nothing to search otherwise
