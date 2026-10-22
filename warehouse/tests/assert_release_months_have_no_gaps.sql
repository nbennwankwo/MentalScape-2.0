-- Months should run without gaps from the first release to the latest.
with months as (
    select distinct release_month from {{ ref('dim_mhsds_release') }}
),
numbered as (
    select
        release_month,
        cast(substr(release_month, 1, 4) as integer) * 12 + cast(substr(release_month, 6, 2) as integer) as month_index,
        lag(cast(substr(release_month, 1, 4) as integer) * 12 + cast(substr(release_month, 6, 2) as integer))
            over (order by release_month) as previous_index
    from months
)
select release_month, month_index - previous_index - 1 as months_missing
from numbered
where previous_index is not null and month_index - previous_index > 1
