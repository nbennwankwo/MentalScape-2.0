{{ config(severity = 'warn') }}
-- Single month England values that move by more than half in one month.
-- Many are real seasonal patterns (see docs/data/mhsds_change_log.md), so this
-- only warns. A sudden rise in warnings after a new release is worth a look.
with england as (
    select measure_id, release_month, max(value_numeric) as value
    from {{ ref('fct_mhsds_values') }}
    where geo_level = 'England' and window_months = 1 and breakdown = 'England' and value_numeric >= 500
    group by measure_id, release_month
),
paired as (
    select
        measure_id,
        release_month,
        value,
        lag(value) over (partition by measure_id order by release_month) as previous_value
    from england
)
select measure_id, release_month, previous_value, value
from paired
where previous_value > 0 and (value / previous_value > 1.5 or value / previous_value < 0.67)
