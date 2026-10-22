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
)

select release_month, sub_icb_code, sub_icb_name, icb_code, icb_name
from matched
where preference = 1
