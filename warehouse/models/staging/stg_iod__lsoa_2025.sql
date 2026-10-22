-- The English Indices of Deprivation 2025, one row per LSOA (2021 boundaries).
--
-- Ranks run from 1, the most deprived, to 33,755. Deciles run from 1, the
-- most deprived tenth of LSOAs, to 10. Scores are not comparable between
-- domains, and IoD 2025 is not comparable with IoD 2019 (config/sources.yaml).
-- The population counts are the mid-2022 denominators MHCLG used.

with source as (
    select * from {{ source('raw', 'ref_iod_2025_file7') }}
)

select
    trim(lsoa_code_2021) as lsoa_code,
    trim(lsoa_name_2021) as lsoa_name,
    trim(local_authority_district_code_2024) as lad24_code,
    trim(local_authority_district_name_2024) as lad24_name,
    {{ safe_to_numeric('index_of_multiple_deprivation_imd_score') }} as imd_score,
    cast(index_of_multiple_deprivation_imd_rank as integer) as imd_rank,
    cast(index_of_multiple_deprivation_imd_decile as integer) as imd_decile,
    {{ safe_to_numeric('income_score_rate') }} as income_rate,
    cast(income_decile as integer) as income_decile,
    {{ safe_to_numeric('employment_score_rate') }} as employment_rate,
    cast(employment_decile as integer) as employment_decile,
    {{ safe_to_numeric('education_skills_and_training_score') }} as education_score,
    cast(education_skills_and_training_decile as integer) as education_decile,
    {{ safe_to_numeric('health_deprivation_and_disability_score') }} as health_score,
    cast(health_deprivation_and_disability_decile as integer) as health_decile,
    {{ safe_to_numeric('crime_score') }} as crime_score,
    cast(crime_decile as integer) as crime_decile,
    {{ safe_to_numeric('barriers_to_housing_and_services_score') }} as barriers_score,
    cast(barriers_to_housing_and_services_decile as integer) as barriers_decile,
    {{ safe_to_numeric('living_environment_score') }} as living_environment_score,
    cast(living_environment_decile as integer) as living_environment_decile,
    {{ safe_to_numeric('income_deprivation_affecting_children_index_idaci_score_rate') }} as idaci_rate,
    cast(income_deprivation_affecting_children_index_idaci_decile as integer) as idaci_decile,
    {{ safe_to_numeric('income_deprivation_affecting_older_people_idaopi_score_rate') }} as idaopi_rate,
    cast(income_deprivation_affecting_older_people_idaopi_decile as integer) as idaopi_decile,
    cast(total_population_mid_2022 as integer) as population_total,
    cast(dependent_children_aged_0_15_mid_2022 as integer) as population_children_0_15,
    cast(older_population_aged_60_and_over_mid_2022 as integer) as population_older_60_plus,
    cast(working_age_population_18_66_mid_2022 as integer) as population_working_age_18_66
from source
