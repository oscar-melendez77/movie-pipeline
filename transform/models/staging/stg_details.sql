-- One row per movie: pick the fields we need out of the raw JSON

select
    id,
    data ->> 'title'                                   as title,
    try_cast(data ->> 'release_date' as date)          as release_date,
    year(try_cast(data ->> 'release_date' as date))    as year,
    nullif(trim(data ->> 'overview'), '')              as overview,

    -- lists: [{"id":..,"name":"Drama"}, ...]  ->  ['Drama', ...]
    -- [*] means "every item in the list"
    json_extract_string(data, '$.genres[*].name')              as genres,
    json_extract_string(data, '$.keywords.keywords[*].name')   as keywords,

    cast(data ->> 'vote_average' as double)            as vote_average,
    cast(data ->> 'vote_count'   as integer)           as vote_count,
    cast(data ->> 'popularity'   as double)            as popularity

from {{ source('raw', 'raw_details') }}
