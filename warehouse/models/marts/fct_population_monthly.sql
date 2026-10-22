-- Population denominators for every release month of MHSDS and NHS Talking
-- Therapies, by area and broad age band, ready for rates per 100,000.
--
-- For each month the warehouse uses the ONS boundaries in force that month
-- and the mid year estimate for that calendar year. Two compromises are
-- recorded in basis_note so they are never hidden.
--   Months before April 2023 use the April 2023 boundaries, because the July
--   2022 lookup is on 2011 LSOAs. The 106 Sub ICB codes are the same.
--   Months after the latest estimate use the latest estimate, mid-2024 at
--   the time of writing, until ONS publishes the next one.

with months as (
    select release_month from {{ ref('dim_mhsds_release') }}
    union
    select release_month from {{ ref('dim_talking_therapies_release') }}
),

editions as (
    select distinct boundary_edition from {{ ref('int_population__area_wide') }}
),

years as (
    select min(population_year) as first_year, max(population_year) as last_year
    from {{ ref('int_population__area_wide') }}
),

basis as (
    select
        m.release_month,
        coalesce(
            (select max(e.boundary_edition) from editions as e where e.boundary_edition <= m.release_month),
            (select min(e.boundary_edition) from editions as e)
        ) as boundary_edition,
        greatest(least(cast(substr(m.release_month, 1, 4) as integer), y.last_year), y.first_year) as population_year,
        y.last_year
    from months as m
    cross join years as y
),

bands as (
    select 'All ages' as age_band, 0 as age_from, 90 as age_to
    union all select '0 to 17', 0, 17
    union all select '18 and over', 18, 90
    union all select '18 to 64', 18, 64
    union all select '65 and over', 65, 90
),

area_bands as (
    select
        p.boundary_edition,
        p.population_year,
        p.geo_level,
        p.geo_code,
        max(p.geo_name) as geo_name,
        b.age_band,
        sum(p.population) as population
    from {{ ref('fct_population') }} as p
    inner join bands as b on p.age between b.age_from and b.age_to
    group by p.boundary_edition, p.population_year, p.geo_level, p.geo_code, b.age_band
)

select
    s.release_month,
    a.geo_level,
    a.geo_code,
    a.geo_name,
    a.age_band,
    a.population,
    s.population_year,
    s.boundary_edition,
    case
        when s.release_month < s.boundary_edition
            then 'April 2023 boundaries used for an earlier month'
        when cast(substr(s.release_month, 1, 4) as integer) > s.last_year
            then 'latest ONS estimate used, mid-' || cast(s.last_year as varchar)
    end as basis_note
from basis as s
inner join area_bands as a
    on a.boundary_edition = s.boundary_edition and a.population_year = s.population_year
