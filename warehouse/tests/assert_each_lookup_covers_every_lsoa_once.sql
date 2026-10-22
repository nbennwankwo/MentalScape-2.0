-- Every English LSOA in the population estimates must appear exactly once in
-- every ONS lookup edition on 2021 LSOAs. Otherwise people would be lost or
-- counted twice when LSOAs are added up to Sub ICBs, ICBs and local authorities.
with lookup as (
    select boundary_edition, lsoa_code, count(*) as appearances
    from {{ ref('stg_ons__lsoa_health_lookup') }}
    where lsoa_vintage = 2021
    group by boundary_edition, lsoa_code
),

editions as (
    select distinct boundary_edition from lookup
),

lsoas as (
    select distinct lsoa_code from {{ ref('stg_ons__lsoa_population') }}
)

select e.boundary_edition, s.lsoa_code, l.appearances
from editions as e
cross join lsoas as s
left join lookup as l on l.boundary_edition = e.boundary_edition and l.lsoa_code = s.lsoa_code
where l.appearances is null or l.appearances <> 1
