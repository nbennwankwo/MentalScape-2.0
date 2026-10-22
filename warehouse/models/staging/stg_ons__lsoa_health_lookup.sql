-- One row per LSOA for each edition of the ONS health geography lookup.
--
-- Each lookup gives two codes for every Sub ICB and ICB. The ONS code starts
-- with E38 or E54. The NHS code, in the columns ending CDH, is the one NHS
-- England publishes, such as 06Q or QH8, so it is the one used to join to
-- MHSDS and NHS Talking Therapies. The July 2022 edition is built on 2011
-- LSOAs and the later ones on 2021 LSOAs.

{%- set editions = [
    ('lsoa11_sicbl_icb_lad_2022', '2022-07', '22', '11'),
    ('lsoa21_sicbl_icb_lad_2023', '2023-04', '23', '21'),
    ('lsoa21_sicbl_icb_lad_2024', '2024-04', '24', '21'),
    ('lsoa21_sicbl_icb_lad_2025', '2025-04', '25', '21'),
    ('lsoa21_sicbl_icb_lad_2026', '2026-04', '26', '21'),
] %}

{% for table, edition, yy, lsoa in editions %}
select
    '{{ edition }}' as boundary_edition,
    {{ 2000 + (lsoa | int) }} as lsoa_vintage,
    trim(lsoa{{ lsoa }}cd) as lsoa_code,
    trim(lsoa{{ lsoa }}nm) as lsoa_name,
    trim(sicbl{{ yy }}cd) as sub_icb_ons_code,
    trim(sicbl{{ yy }}cdh) as sub_icb_code,
    trim(sicbl{{ yy }}nm) as sub_icb_name,
    trim(icb{{ yy }}cd) as icb_ons_code,
    trim(icb{{ yy }}cdh) as icb_code,
    trim(icb{{ yy }}nm) as icb_name,
    trim(lad{{ yy }}cd) as lad_code,
    trim(lad{{ yy }}nm) as lad_name
from {{ source('raw', 'ref_' ~ table) }}
{% if not loop.last %}union all{% endif %}
{% endfor %}
