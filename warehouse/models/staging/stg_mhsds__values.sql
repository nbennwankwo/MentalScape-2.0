-- One row per published value, cleaned and typed but otherwise unchanged.
-- Nothing is dropped here. Suppressed values keep is_suppressed = true and a null number.

with source as (
    select * from {{ source('raw', 'mhsds_main') }}
),

typed as (
    select
        _reporting_month as release_month,
        _version as file_version,
        cast(_revision as integer) as file_revision,
        _asset_name as asset_name,
        {{ parse_nhs_date('reporting_period_start') }} as period_start,
        {{ parse_nhs_date('reporting_period_end') }} as period_end,
        trim(status) as status,
        trim(breakdown) as breakdown,
        trim(split_part(breakdown, ';', 1)) as geo_label,
        case
            when strpos(breakdown, ';') > 0 then trim(substr(breakdown, strpos(breakdown, ';') + 1))
        end as breakdown_dimension,
        trim(primary_level) as primary_code,
        trim(primary_level_description) as primary_name,
        trim(secondary_level) as secondary_code,
        trim(secondary_level_description) as secondary_name,
        trim(measure_id) as measure_id,
        trim(regexp_replace(measure_name, '\s+', ' ', 'g')) as measure_name,
        trim(measure_value) as value_text,
        trim(measure_value) = '*' as is_suppressed,
        {{ safe_to_numeric('measure_value') }} as value_numeric
    from source
)

select
    *,
    {{ canonical_geo_level('geo_label') }} as geo_level,
    {{ window_months('period_start', 'period_end') }} as window_months
from typed
