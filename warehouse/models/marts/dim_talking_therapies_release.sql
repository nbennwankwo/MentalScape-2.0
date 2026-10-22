-- One row per NHS Talking Therapies release month: which file was used, which
-- other versions exist, and how many values it gave.

with files as (
    select * from {{ ref('stg_talking_therapies__files') }} where kind = 'activity'
),

versions as (
    select reporting_month, count(*) as versions_collected
    from files
    group by reporting_month
),

loaded as (
    select
        release_month,
        count(*) as values_loaded,
        sum(case when is_suppressed then 1 else 0 end) as values_suppressed,
        count(distinct case when geo_level = 'Sub ICB' then sub_icb_code end) as sub_icbs
    from {{ ref('fct_talking_therapies_values') }}
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
    l.values_suppressed,
    l.sub_icbs
from files as f
join versions as v on v.reporting_month = f.reporting_month
join loaded as l on l.release_month = f.reporting_month
where f.is_preferred
