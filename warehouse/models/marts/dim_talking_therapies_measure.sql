-- One row per NHS Talking Therapies measure ID ever published, with its
-- statistic, lifetime and how many names it has had.

with by_release as (
    select measure_id, measure_name, statistic, release_month, count(*) as rows_published
    from {{ ref('fct_talking_therapies_values') }}
    group by measure_id, measure_name, statistic, release_month
),

latest_name as (
    select
        measure_id,
        measure_name,
        statistic,
        row_number() over (partition by measure_id order by release_month desc, measure_name) as recency
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

latest_release as (
    select max(release_month) as release_month from by_release
)

select
    s.measure_id,
    n.measure_name as latest_name,
    n.statistic,
    s.first_release_month,
    s.last_release_month,
    s.last_release_month = l.release_month as in_latest_release,
    s.releases_present,
    s.name_versions
from spans as s
join latest_name as n on n.measure_id = s.measure_id and n.recency = 1
cross join latest_release as l
