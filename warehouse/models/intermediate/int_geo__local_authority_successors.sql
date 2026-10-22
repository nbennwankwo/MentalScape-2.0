-- What replaced each local authority abolished on 1 April 2023.
--
-- Built only from ONS lookups, never typed by hand. Districts come from the
-- 2022 to 2023 district lookup. A county is abolished when it has districts in
-- 2022 but none in 2023, and its successors are whatever its districts became.
--
--     merged         a district joined others in a new unitary authority
--     same area      a county became one unitary authority covering exactly
--                    the same districts, so its series can continue
--     split          a county was divided between two or more authorities,
--                    so its series cannot continue, as with Cumbria

with lookups as (
    select * from {{ ref('stg_ons__local_authority_lookups') }}
),

district_changes as (
    select distinct
        lad22_code as old_code,
        lad22_name as old_name,
        'district' as old_tier,
        lad23_code as new_code,
        lad23_name as new_name
    from lookups
    where lad22_code <> lad23_code
),

counties_2023 as (
    select distinct county23_code from lookups where county23_code is not null
),

county_changes as (
    select distinct
        county22_code as old_code,
        county22_name as old_name,
        'county' as old_tier,
        lad23_code as new_code,
        lad23_name as new_name
    from lookups
    where county22_code is not null
        and county22_code not in (select county23_code from counties_2023)
),

changes as (
    select * from district_changes
    union all
    select * from county_changes
),

-- A successor covers the same area as a county when every district that
-- became the successor was in that county.
outside_districts as (
    select c.old_code, c.new_code, count(l.lad22_code) as districts_from_elsewhere
    from county_changes as c
    left join lookups as l
        on l.lad23_code = c.new_code and coalesce(l.county22_code, '') <> c.old_code
    group by c.old_code, c.new_code
),

counted as (
    select
        c.*,
        count(*) over (partition by c.old_code) as successors,
        coalesce(o.districts_from_elsewhere, 0) as districts_from_elsewhere
    from changes as c
    left join outside_districts as o on o.old_code = c.old_code and o.new_code = c.new_code
)

select
    old_code,
    old_name,
    old_tier,
    new_code,
    new_name,
    successors,
    case
        when successors > 1 then 'split'
        when old_tier = 'county' and districts_from_elsewhere = 0 then 'same area'
        else 'merged'
    end as change_type,
    '2023-04' as effective_month
from counted
