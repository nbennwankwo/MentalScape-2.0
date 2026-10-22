-- One row per release month: which file was used, which other versions exist,
-- and how many values were loaded from it.

with files as (
    select * from {{ ref('stg_mhsds__files') }} where kind = 'main'
),

versions as (
    select reporting_month, count(*) as versions_collected
    from files
    group by reporting_month
),

loaded as (
    select release_month, count(*) as values_loaded, sum(case when is_suppressed then 1 else 0 end) as values_suppressed
    from {{ ref('fct_mhsds_values') }}
    group by release_month
)

select
    f.reporting_month as release_month,
    f.version as version_used,
    f.revision as revision_used,
    f.asset_name,
    f.source_url,
    f.stored_sha256,
    v.versions_collected,
    l.values_loaded,
    l.values_suppressed
from files as f
join versions as v on v.reporting_month = f.reporting_month
join loaded as l on l.release_month = f.reporting_month
where f.is_preferred
