-- ONS mid year population estimates for each English LSOA (2021 boundaries),
-- one row per LSOA and year, with one column per single year of age and sex.
--
-- The workbook has one sheet per year, named like "Mid-2024 LSOA 2021", and
-- the loader keeps the sheet name in _sheet. Welsh LSOAs are dropped.
-- f90 and m90 mean 90 and over.

select
    cast(substr(_sheet, 5, 4) as integer) as population_year,
    trim(lsoa_2021_code) as lsoa_code,
    trim(lsoa_2021_name) as lsoa_name,
    trim(lad_2023_code) as lad23_code,
    cast(total as integer) as total,
    {%- for column in population_age_columns() %}
    cast({{ column }} as integer) as {{ column }}{{ "," if not loop.last }}
    {%- endfor %}
from {{ source('raw', 'ref_ons_lsoa_population_2022_2024') }}
where trim(lsoa_2021_code) like 'E%'
