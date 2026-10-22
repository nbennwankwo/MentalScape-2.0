-- The Indices of Deprivation 2025 summarised for every Sub ICB, ICB and local
-- authority, on each edition of the ONS boundaries since April 2023.
--
-- MHCLG publishes summaries for local authorities only, so the warehouse
-- builds them for every area in the same way, from LSOAs.
--   imd_average_score       the population weighted mean of LSOA IMD scores,
--                           MHCLG's "average score" measure
--   share_most_deprived_*   the share of the population living in LSOAs in
--                           England's most deprived 10 or 20 percent
--   income, employment and children's rates are the share of the relevant
--   population that is income or employment deprived, weighted by that
--   population, as MHCLG's "scale" measures are
-- Higher means more deprived for every measure. imd_average_score_rank is 1
-- for the most deprived area of each level and edition.

with iod as (
    select * from {{ ref('stg_iod__lsoa_2025') }}
),

lookup as (
    select boundary_edition, lsoa_code, sub_icb_code, sub_icb_name, icb_code, icb_name, lad_code, lad_name
    from {{ ref('stg_ons__lsoa_health_lookup') }}
    where lsoa_vintage = 2021
),

joined as (
    select l.boundary_edition, l.sub_icb_code, l.sub_icb_name, l.icb_code, l.icb_name, l.lad_code, l.lad_name, i.*
    from iod as i
    inner join lookup as l on l.lsoa_code = i.lsoa_code
),

{% set levels = [
    ('Sub ICB', 'sub_icb_code', 'sub_icb_name'),
    ('ICB', 'icb_code', 'icb_name'),
    ('Local Authority', 'lad_code', 'lad_name'),
] %}

summaries as (
    {% for level, code, name in levels %}
    select
        boundary_edition,
        '{{ level }}' as geo_level,
        {{ code }} as geo_code,
        max({{ name }}) as geo_name,
        count(*) as lsoas,
        sum(population_total) as population_mid_2022,
        sum(imd_score * population_total) / nullif(sum(population_total), 0) as imd_average_score,
        sum(case when imd_decile = 1 then population_total else 0 end) * 1.0
            / nullif(sum(population_total), 0) as share_most_deprived_decile,
        sum(case when imd_decile <= 2 then population_total else 0 end) * 1.0
            / nullif(sum(population_total), 0) as share_most_deprived_quintile,
        sum(income_rate * population_total) / nullif(sum(population_total), 0) as income_deprived_rate,
        sum(employment_rate * population_working_age_18_66)
            / nullif(sum(population_working_age_18_66), 0) as employment_deprived_rate,
        sum(idaci_rate * population_children_0_15)
            / nullif(sum(population_children_0_15), 0) as children_income_deprived_rate,
        sum(health_score * population_total) / nullif(sum(population_total), 0) as health_average_score
    from joined
    group by boundary_edition, {{ code }}
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
)

select
    *,
    rank() over (partition by boundary_edition, geo_level order by imd_average_score desc) as imd_average_score_rank
from summaries
