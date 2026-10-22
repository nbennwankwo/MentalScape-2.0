-- Sub ICB codes in NHS Talking Therapies that MHSDS did not publish that
-- month, so they have no ICB. Commissioning hubs and placeholder codes are
-- already set aside in staging, so any result here is a code nobody has seen,
-- and ICB totals built from Sub ICBs would be missing its people.
{{ config(severity = 'warn') }}

select distinct release_month, sub_icb_code, org_name1
from {{ ref('fct_talking_therapies_values') }}
where geo_level = 'Sub ICB' and icb_code is null and {{ is_real_code('sub_icb_code') }}
