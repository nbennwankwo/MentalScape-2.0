-- A file for month M should never contain values for periods ending after M.
-- Rows returned here would point to a misclassified file or a misread date.
select release_month, period_end, count(*) as rows_found
from {{ ref('stg_mhsds__values') }}
where cast(extract(year from period_end) as integer) * 100 + cast(extract(month from period_end) as integer)
    > cast(replace(release_month, '-', '') as integer)
group by release_month, period_end
