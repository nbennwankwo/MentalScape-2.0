-- ONS mid year population estimates by single year of age and sex for every
-- Sub ICB, ICB, local authority and England, on each edition of the ONS
-- boundaries since April 2023. Age 90 means 90 and over.
--
-- Pick the boundary edition in force in the month you are working with, or
-- use fct_population_monthly, which has already done that.

{% for column in population_age_columns() %}
select
    boundary_edition,
    population_year,
    geo_level,
    geo_code,
    geo_name,
    '{{ column[0] | upper }}' as sex,
    {{ column[1:] }} as age,
    {{ column }} as population
from {{ ref('int_population__area_wide') }}
{% if not loop.last %}union all{% endif %}
{% endfor %}
