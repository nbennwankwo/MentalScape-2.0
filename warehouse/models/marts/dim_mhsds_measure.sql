-- One row per measure ID ever published, with its lifetime, the reporting
-- windows it uses and any NHS England data quality caveat that applies.

with by_release as (
    select measure_id, measure_name, release_month, window_months, count(*) as rows_published
    from {{ ref('fct_mhsds_values') }}
    group by measure_id, measure_name, release_month, window_months
),

latest_name as (
    select
        measure_id,
        measure_name,
        row_number() over (partition by measure_id order by release_month desc, window_months, measure_name) as recency
    from by_release
),

spans as (
    select
        measure_id,
        min(release_month) as first_release_month,
        max(release_month) as last_release_month,
        count(distinct release_month) as releases_present,
        count(distinct measure_name) as name_versions
    from by_release
    group by measure_id
),

windows as (
    select
        measure_id,
        string_agg(distinct cast(window_months as varchar), ',' order by cast(window_months as varchar)) as windows
    from by_release
    group by measure_id
),

caveats as (
    select m.measure_id, string_agg(c.caveat, ' ' order by c.caveat) as caveats
    from spans as m
    join {{ ref('mhsds_measure_caveats') }} as c on m.measure_id like c.measure_pattern
    group by m.measure_id
),

latest_release as (
    select max(release_month) as release_month from by_release
)

select
    s.measure_id,
    upper(regexp_replace(s.measure_id, '[^A-Za-z].*$', '')) as family,
    n.measure_name as latest_name,
    s.first_release_month,
    s.last_release_month,
    s.last_release_month = l.release_month as in_latest_release,
    s.releases_present,
    s.name_versions,
    w.windows,
    c.caveats
from spans as s
join latest_name as n on n.measure_id = s.measure_id and n.recency = 1
join windows as w on w.measure_id = s.measure_id
cross join latest_release as l
left join caveats as c on c.measure_id = s.measure_id
