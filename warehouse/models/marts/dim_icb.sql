-- One row per ICB code ever published, with its latest name and whether it
-- still exists. The twelve ICBs abolished on 1 April 2026 show as retired.

with icbs as (
    select distinct release_month, primary_code as icb_code, primary_name as icb_name
    from {{ ref('stg_mhsds__values') }}
    where geo_level = 'ICB' and {{ is_real_code('primary_code') }}
),

latest_release as (
    select max(release_month) as release_month from {{ ref('stg_mhsds__values') }}
),

ranked as (
    select *, row_number() over (partition by icb_code order by release_month desc, icb_name) as recency
    from icbs
),

spans as (
    select icb_code, min(release_month) as first_release_month, max(release_month) as last_release_month
    from icbs
    group by icb_code
)

select
    r.icb_code,
    r.icb_name as latest_name,
    s.first_release_month,
    s.last_release_month,
    case when s.last_release_month = l.release_month then 'current' else 'retired' end as status
from ranked as r
join spans as s on s.icb_code = r.icb_code
cross join latest_release as l
where r.recency = 1
