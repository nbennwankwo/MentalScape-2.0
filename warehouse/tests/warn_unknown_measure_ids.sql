-- Measure IDs in the warehouse that the change log has never seen.
--
-- NHS England adds measures often, so this warns rather than fails. A result
-- here means a new release brought new measures. Profile it and run
-- make changelog, which refreshes seeds/mhsds_known_measures.csv, and check
-- docs/data/mhsds_change_log.md before using the new measures.
{{ config(severity = 'warn') }}

select distinct v.measure_id, v.release_month
from {{ ref('stg_mhsds__values') }} as v
left join {{ ref('mhsds_known_measures') }} as k
    on k.measure_id = v.measure_id
where k.measure_id is null
