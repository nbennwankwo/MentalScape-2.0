-- Every NHS Talking Therapies release should list values for every Sub ICB.
-- Far fewer would mean a broken file.
select release_month, sub_icbs
from {{ ref('dim_talking_therapies_release') }}
where sub_icbs < {{ var('min_sub_icbs_per_release') }}
