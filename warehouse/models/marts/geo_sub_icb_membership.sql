-- Dated membership of Sub ICBs in ICBs. One row per unbroken run of months in
-- which a Sub ICB belonged to the same ICB. The April 2026 mergers appear as a
-- new row starting in 2026-04 (docs/adr/0004).

with monthly as (
    select * from {{ ref('int_geo__sub_icb_monthly') }}
),

flagged as (
    select
        *,
        case
            when lag(icb_code) over (partition by sub_icb_code order by release_month) is distinct from icb_code
            then 1 else 0
        end as starts_new_run
    from monthly
),

runs as (
    select
        *,
        sum(starts_new_run) over (
            partition by sub_icb_code order by release_month rows between unbounded preceding and current row
        ) as run_number
    from flagged
)

select
    sub_icb_code,
    icb_code,
    max(icb_name) as icb_name,
    min(release_month) as valid_from_month,
    max(release_month) as valid_to_month,
    count(*) as releases,
    sum(case when icb_source = 'carried forward from previous month' then 1 else 0 end) as months_carried_forward
from runs
group by sub_icb_code, icb_code, run_number
