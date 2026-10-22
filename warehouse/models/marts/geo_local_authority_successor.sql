-- The successor of every local authority abolished in the April 2023
-- reorganisation, with how its figures relate to the successor's.
-- MHSDS publishes one measure at this level, MHS26 delayed discharge days
-- (docs/data/mhsds_change_log.md). Only a 'same area' change lets a series
-- run on unbroken. Suppressed values are never added up to bridge a change.

select * from {{ ref('int_geo__local_authority_successors') }}
