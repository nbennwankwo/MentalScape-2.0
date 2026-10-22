-- Which ICB each Sub ICB belonged to in each release month.
--
-- Sub ICB names embed their parent ICB, for example "NHS ESSEX ICB - 06Q".
-- Some files give one code two names, an old one and a new one (see
-- docs/data/mhsds_change_log.md). The name whose parent ICB actually appears in
-- that month's ICB level rows is the one used.

with sub_icb_names as (
    select distinct
        release_month,
        primary_code as sub_icb_code,
        primary_name as sub_icb_name,
        upper(trim(regexp_replace(primary_name, '\s*-\s*[A-Za-z0-9]+$', ''))) as parent_key
    from {{ ref('stg_mhsds__values') }}
    where geo_level = 'Sub ICB' and {{ is_real_code('primary_code') }}
),

icb_names as (
    select distinct
        release_month,
        primary_code as icb_code,
        primary_name as icb_name,
        upper(trim(replace(upper(primary_name), ' INTEGRATED CARE BOARD', ' ICB'))) as icb_key
    from {{ ref('stg_mhsds__values') }}
    where geo_level = 'ICB' and {{ is_real_code('primary_code') }}
),

matched as (
    select
        s.release_month,
        s.sub_icb_code,
        s.sub_icb_name,
        i.icb_code,
        i.icb_name,
        row_number() over (
            partition by s.release_month, s.sub_icb_code
            order by case when i.icb_code is null then 1 else 0 end, s.sub_icb_name, i.icb_code
        ) as preference
    from sub_icb_names as s
    left join icb_names as i
        on i.release_month = s.release_month and i.icb_key = s.parent_key
),

best as (
    select release_month, sub_icb_code, sub_icb_name, icb_code, icb_name
    from matched
    where preference = 1
)

-- The March 2026 final file was produced after the April 2026 mergers, so it
-- gives some Sub ICBs only their new names while its ICB rows are still the old
-- ICBs. No name matches. In that case the ICB matched in the Sub ICB's
-- previous release is used and icb_source says so. Only one step is carried,
-- so two unmatched releases in a row leave the second one unmatched, and the
-- not_null test on membership warns about it.
select
    release_month,
    sub_icb_code,
    sub_icb_name,
    coalesce(icb_code, lag(icb_code) over (partition by sub_icb_code order by release_month)) as icb_code,
    coalesce(icb_name, lag(icb_name) over (partition by sub_icb_code order by release_month)) as icb_name,
    case
        when icb_code is not null then 'matched by name'
        when lag(icb_code) over (partition by sub_icb_code order by release_month) is not null
            then 'carried forward from previous month'
        else 'unmatched'
    end as icb_source
from best
