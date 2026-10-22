-- Deciles are bands of ranks, so every LSOA in decile 1 must be ranked as more
-- deprived than every LSOA in decile 2, and so on.
with bands as (
    select imd_decile, min(imd_rank) as first_rank, max(imd_rank) as last_rank
    from {{ ref('stg_iod__lsoa_2025') }}
    group by imd_decile
)

select b.imd_decile, b.last_rank, n.imd_decile as next_decile, n.first_rank as next_first_rank
from bands as b
inner join bands as n on n.imd_decile = b.imd_decile + 1
where b.last_rank >= n.first_rank
