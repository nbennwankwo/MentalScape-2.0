-- One row per published NHS Talking Therapies value, cleaned and typed.
--
-- The files before and after the May 2023 rename from IAPT share the same ten
-- columns. Each row has two organisation slots. ORG_CODE1 holds England, a
-- commissioning region or a Sub ICB, and ORG_CODE2 holds a provider, with
-- "all" in a slot that is not used. GROUP_TYPE says which slots are filled.
-- Nothing is dropped. Suppressed values keep is_suppressed = true and a null number.

with source as (
    select * from {{ source('raw', 'talking_therapies_activity') }}
),

typed as (
    select
        _reporting_month as release_month,
        _version as file_version,
        cast(_revision as integer) as file_revision,
        _asset_name as asset_name,
        {{ parse_nhs_date('reporting_period_start') }} as period_start,
        {{ parse_nhs_date('reporting_period_end') }} as period_end,
        trim(group_type) as group_type,
        trim(org_code1) as org_code1,
        trim(org_name1) as org_name1,
        trim(org_code2) as org_code2,
        trim(org_name2) as org_name2,
        trim(measure_id) as measure_id,
        trim(measure_name) as measure_name,
        trim(measure_value_suppressed) as value_text,
        trim(measure_value_suppressed) = '*' as is_suppressed,
        {{ safe_to_numeric('measure_value_suppressed') }} as value_numeric
    from source
),

flagged as (
    select
        *,
        -- NHS England's commissioning hubs, such as the Health and Justice hubs
        -- for prisons and secure settings, are listed among the Sub ICBs but
        -- are not places and belong to no ICB. Their activity is still part of
        -- the England totals.
        group_type in ('SubICB', 'SubICB/Provider') and upper(org_name1) like '%COMMISSIONING HUB%' as is_hub
    from typed
)

select
    *,
    case
        when group_type = 'England' then 'England'
        when group_type = 'CommissioningRegion' then 'Commissioning Region'
        when group_type = 'SubICB' and is_hub then 'Commissioning Hub'
        when group_type = 'SubICB' then 'Sub ICB'
        when group_type = 'Provider' then 'Provider'
        when group_type = 'SubICB/Provider' and is_hub then 'Commissioning Hub and Provider'
        when group_type = 'SubICB/Provider' then 'Sub ICB and Provider'
        else group_type
    end as geo_level,
    case
        when group_type in ('SubICB', 'SubICB/Provider') and not is_hub and {{ is_real_code('org_code1') }}
            then org_code1
    end as sub_icb_code,
    case when is_hub then org_code1 end as hub_code,
    case when group_type = 'CommissioningRegion' then org_code1 end as region_code,
    case when group_type in ('Provider', 'SubICB/Provider') then org_code2 end as provider_code,
    -- Measure names start with the statistic, for example Count_ or Mean_.
    split_part(measure_name, '_', 1) as statistic,
    {{ window_months('period_start', 'period_end') }} as window_months
from flagged
