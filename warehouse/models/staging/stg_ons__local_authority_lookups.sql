-- ONS lookups that describe the April 2023 local government reorganisation.
--
-- One row per 2022 local authority district, with the district or unitary
-- authority it became in April 2023 and the county it sat in before and
-- after. Districts outside two tier areas have no county.

with districts as (
    select
        trim(lad22cd) as lad22_code,
        trim(lad22nm) as lad22_name,
        trim(lad23cd) as lad23_code,
        trim(lad23nm) as lad23_name
    from {{ source('raw', 'ref_lad22_lad23') }}
    where trim(lad22cd) like 'E%'
),

county_2022 as (
    select trim(lad22cd) as lad_code, trim(cty22cd) as county_code, trim(cty22nm) as county_name
    from {{ source('raw', 'ref_lad22_cty22') }}
),

county_2023 as (
    select trim(lad23cd) as lad_code, trim(cty23cd) as county_code, trim(cty23nm) as county_name
    from {{ source('raw', 'ref_lad23_cty23') }}
)

select
    d.lad22_code,
    d.lad22_name,
    d.lad23_code,
    d.lad23_name,
    c22.county_code as county22_code,
    c22.county_name as county22_name,
    c23.county_code as county23_code,
    c23.county_name as county23_name
from districts as d
left join county_2022 as c22 on c22.lad_code = d.lad22_code
left join county_2023 as c23 on c23.lad_code = d.lad23_code
