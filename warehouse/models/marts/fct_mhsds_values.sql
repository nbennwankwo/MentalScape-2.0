-- The analysis ready MHSDS values. One row per release month, reporting
-- window, breakdown, organisation or area, secondary category and measure.
-- The reporting window is part of the key because some measure IDs, such as
-- MHS32, are published for more than one window in the same file.

select
    release_month,
    file_version,
    period_start,
    period_end,
    window_months,
    breakdown,
    geo_level,
    breakdown_dimension,
    primary_code,
    primary_name,
    secondary_code,
    secondary_name,
    measure_id,
    measure_name,
    is_suppressed,
    value_numeric,
    value_text
from {{ ref('stg_mhsds__values') }}
