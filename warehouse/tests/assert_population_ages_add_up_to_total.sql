-- In the ONS workbook the single years of age for both sexes add up exactly
-- to each LSOA's total. A difference would mean a column was misread.
select population_year, lsoa_code, total
from {{ ref('stg_ons__lsoa_population') }}
where total <> {% for column in population_age_columns() %}{{ column }}{{ " + " if not loop.last }}{% endfor %}
