-- The analysis ready NHS Talking Therapies values. One row per release month,
-- organisation slot pair and measure.
--
-- The ICB of each Sub ICB is added from the warehouse's dated membership, the
-- same one used for MHSDS, so both series roll up to the same ICBs in every
-- month. NHS England publishes no ICB level for this series. Counts can be
-- added up to ICB only where no Sub ICB value is suppressed, and rates,
-- means and medians never can (docs/data/pipeline.md).

with values_ as (
    select * from {{ ref('stg_talking_therapies__values') }}
),

membership as (
    select release_month, sub_icb_code, icb_code
    from {{ ref('int_geo__sub_icb_monthly') }}
)

select
    v.release_month,
    v.file_version,
    v.period_start,
    v.period_end,
    v.window_months,
    v.group_type,
    v.geo_level,
    v.org_code1,
    v.org_name1,
    v.org_code2,
    v.org_name2,
    v.sub_icb_code,
    m.icb_code,
    v.hub_code,
    v.region_code,
    v.provider_code,
    v.measure_id,
    v.measure_name,
    v.statistic,
    v.is_suppressed,
    v.value_numeric,
    v.value_text
from values_ as v
left join membership as m
    on m.release_month = v.release_month and m.sub_icb_code = v.sub_icb_code
