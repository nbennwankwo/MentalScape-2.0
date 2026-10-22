-- The English Indices of Deprivation 2025 for every LSOA, with the Sub ICB,
-- ICB and local authority each LSOA sits in under the April 2026 ONS lookup.

with iod as (
    select * from {{ ref('stg_iod__lsoa_2025') }}
),

latest_lookup as (
    select *
    from {{ ref('stg_ons__lsoa_health_lookup') }}
    where boundary_edition = (select max(boundary_edition) from {{ ref('stg_ons__lsoa_health_lookup') }})
)

select
    i.*,
    l.boundary_edition,
    l.sub_icb_code,
    l.icb_code,
    l.lad_code
from iod as i
left join latest_lookup as l on l.lsoa_code = i.lsoa_code
