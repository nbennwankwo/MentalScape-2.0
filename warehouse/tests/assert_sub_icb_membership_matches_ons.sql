-- The ICB the warehouse works out for each Sub ICB from MHSDS names must agree
-- with the ONS lookup in force that month. Months before the first ONS
-- edition are not checked. A result here means either the name matching went
-- wrong or NHS England and ONS disagree, and either needs a person to look.

with ours as (
    select release_month, sub_icb_code, icb_code, icb_source
    from {{ ref('int_geo__sub_icb_monthly') }}
),

ons as (
    select * from {{ ref('int_geo__ons_sub_icb_membership') }}
),

in_force as (
    select
        o.*,
        (select max(e.boundary_edition) from ons as e where e.boundary_edition <= o.release_month) as boundary_edition
    from ours as o
)

select
    f.release_month,
    f.sub_icb_code,
    f.icb_code,
    f.icb_source,
    f.boundary_edition,
    n.icb_code as ons_icb_code
from in_force as f
left join ons as n on n.boundary_edition = f.boundary_edition and n.sub_icb_code = f.sub_icb_code
where f.boundary_edition is not null
    and (n.icb_code is null or n.icb_code <> f.icb_code)
