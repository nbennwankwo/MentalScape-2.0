-- One row per Sub ICB code ever published, with its latest name and its ICB on
-- the latest boundaries. Codes that stop appearing, such as Frimley (D4U1Y)
-- after the April 2026 changes, are marked retired rather than dropped.

with monthly as (
    select * from {{ ref('int_geo__sub_icb_monthly') }}
),

latest_release as (
    select max(release_month) as release_month from monthly
),

ranked as (
    select *, row_number() over (partition by sub_icb_code order by release_month desc) as recency
    from monthly
),

spans as (
    select sub_icb_code, min(release_month) as first_release_month, max(release_month) as last_release_month,
           count(*) as releases_present
    from monthly
    group by sub_icb_code
)

select
    r.sub_icb_code,
    r.sub_icb_name as latest_name,
    s.first_release_month,
    s.last_release_month,
    s.releases_present,
    case when s.last_release_month = l.release_month then 'current' else 'retired' end as status,
    case when s.last_release_month = l.release_month then r.icb_code end as current_icb_code,
    case when s.last_release_month = l.release_month then r.icb_name end as current_icb_name
from ranked as r
join spans as s on s.sub_icb_code = r.sub_icb_code
cross join latest_release as l
where r.recency = 1
