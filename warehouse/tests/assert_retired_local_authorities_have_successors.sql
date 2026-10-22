-- Every local authority code MHSDS stopped publishing at the April 2023
-- reorganisation must have a successor in the ONS lookups.
select la_code, la_name, last_month
from {{ ref('dim_local_authority') }}
where last_month = '2023-03' and successor_codes is null
