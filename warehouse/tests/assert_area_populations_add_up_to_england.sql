-- For every boundary edition and year, the Sub ICBs, the ICBs and the local
-- authorities must each add up to the England total.
with totals as (
    select boundary_edition, population_year, geo_level, sum(total) as population
    from {{ ref('int_population__area_wide') }}
    group by boundary_edition, population_year, geo_level
)

select t.boundary_edition, t.population_year, t.geo_level, t.population, e.population as england
from totals as t
inner join totals as e
    on e.boundary_edition = t.boundary_edition and e.population_year = t.population_year and e.geo_level = 'England'
where t.population <> e.population
