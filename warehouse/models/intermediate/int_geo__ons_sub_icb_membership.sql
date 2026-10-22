-- The ICB each Sub ICB belongs to in each edition of the ONS lookup, with the
-- months that edition was in force. Used to check the membership the
-- warehouse works out from MHSDS names (int_geo__sub_icb_monthly).

with pairs as (
    select distinct boundary_edition, sub_icb_code, sub_icb_name, icb_code, icb_name
    from {{ ref('stg_ons__lsoa_health_lookup') }}
),

editions as (
    select boundary_edition, lead(boundary_edition) over (order by boundary_edition) as next_edition
    from (select distinct boundary_edition from pairs) as e
)

select
    p.boundary_edition,
    p.boundary_edition as valid_from_month,
    e.next_edition as next_edition_month,
    p.sub_icb_code,
    p.sub_icb_name,
    p.icb_code,
    p.icb_name
from pairs as p
inner join editions as e on e.boundary_edition = p.boundary_edition
