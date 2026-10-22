-- Every local authority code MHSDS has published, with its tier, lifetime
-- and, for authorities abolished in April 2023, what replaced it.

with published as (
    select release_month, primary_code as la_code, primary_name as la_name
    from {{ ref('stg_mhsds__values') }}
    where geo_level = 'Local Authority' and {{ is_real_code('primary_code') }}
),

lifetime as (
    select la_code, min(release_month) as first_month, max(release_month) as last_month
    from published
    group by la_code
),

-- A code can carry two names across files, so the name from its last month wins.
latest_name as (
    select p.la_code, max(p.la_name) as la_name
    from published as p
    inner join lifetime as l on l.la_code = p.la_code and l.last_month = p.release_month
    group by p.la_code
),

latest_release as (
    select max(release_month) as release_month from {{ ref('stg_mhsds__values') }}
),

successors as (
    select
        old_code,
        max(change_type) as change_type,
        string_agg(new_code, ',' order by new_code) as successor_codes
    from {{ ref('int_geo__local_authority_successors') }}
    group by old_code
)

select
    l.la_code,
    n.la_name,
    case left(l.la_code, 3)
        when 'E06' then 'unitary authority'
        when 'E07' then 'district'
        when 'E08' then 'metropolitan district'
        when 'E09' then 'London borough'
        when 'E10' then 'county'
        else 'other'
    end as tier,
    l.first_month,
    l.last_month,
    -- Abolished only when ONS records a successor. A code can also simply stop
    -- appearing, as Barnsley and Sheffield did after March 2025 although both
    -- councils still exist (docs/data/mhsds_change_log.md).
    case
        when l.last_month = r.release_month then 'current'
        when s.old_code is not null then 'abolished'
        else 'not in latest release'
    end as status,
    s.change_type,
    s.successor_codes
from lifetime as l
inner join latest_name as n on n.la_code = l.la_code
cross join latest_release as r
left join successors as s on s.old_code = l.la_code
