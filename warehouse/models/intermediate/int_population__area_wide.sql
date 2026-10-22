{{ config(materialized='table') }}

-- ONS LSOA population estimates added up to Sub ICB, ICB, local authority
-- and England, once for each edition of the ONS LSOA lookup on 2021 LSOAs.
-- This is how ONS builds its own estimates for health geographies, and it
-- gives figures on the April 2026 ICB boundaries before ONS publishes its
-- own (docs/adr/0012). Still wide, one column per single year of age and sex.
-- The July 2022 lookup is on 2011 LSOAs, so it cannot be used here.

with population as (
    select * from {{ ref('stg_ons__lsoa_population') }}
),

lookup as (
    select boundary_edition, lsoa_code, sub_icb_code, sub_icb_name, icb_code, icb_name, lad_code, lad_name
    from {{ ref('stg_ons__lsoa_health_lookup') }}
    where lsoa_vintage = 2021
),

joined as (
    select l.boundary_edition, l.sub_icb_code, l.sub_icb_name, l.icb_code, l.icb_name, l.lad_code, l.lad_name, p.*
    from population as p
    inner join lookup as l on l.lsoa_code = p.lsoa_code
)

{% set levels = [
    ('Sub ICB', 'sub_icb_code', 'sub_icb_name'),
    ('ICB', 'icb_code', 'icb_name'),
    ('Local Authority', 'lad_code', 'lad_name'),
    ('England', "'E92000001'", "'England'"),
] %}

{% for level, code, name in levels %}
select
    boundary_edition,
    population_year,
    '{{ level }}' as geo_level,
    {{ code }} as geo_code,
    max({{ name }}) as geo_name,
    count(*) as lsoas,
    sum(total) as total,
    {%- for column in population_age_columns() %}
    sum({{ column }}) as {{ column }}{{ "," if not loop.last }}
    {%- endfor %}
from joined
group by boundary_edition, population_year{% if not code.startswith("'") %}, {{ code }}{% endif %}
{% if not loop.last %}union all{% endif %}
{% endfor %}
