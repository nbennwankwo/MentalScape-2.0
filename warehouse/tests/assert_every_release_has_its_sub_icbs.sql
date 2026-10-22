-- Every release since July 2022 lists 106 Sub ICBs. A release with far fewer
-- would mean a broken file or a broken geography mapping.
select release_month, count(distinct primary_code) as sub_icbs
from {{ ref('stg_mhsds__values') }}
where geo_level = 'Sub ICB' and {{ is_real_code('primary_code') }}
group by release_month
having count(distinct primary_code) < {{ var('min_sub_icbs_per_release') }}
