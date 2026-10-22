# SQL

The warehouse and its dbt project live in [`warehouse/`](../warehouse) (see [ADR 0002](../docs/adr/0002-sql-warehouse-postgres-and-dbt.md) and the [pipeline guide](../docs/data/pipeline.md)).

This folder holds hand written exploration queries that run in DuckDB against the raw files. For example, the query below lists every measure in a release with its suppression rate.

```sql
SELECT
    trim(MEASURE_ID) AS measure_id,
    any_value(trim(MEASURE_NAME)) AS measure_name,
    count(*) AS n_rows,
    avg((trim(MEASURE_VALUE) = '*')::INT) AS share_suppressed
FROM read_csv('data/raw/mhsds_monthly/MHSDS Data_AugPerf_2026.csv', all_varchar = true)
GROUP BY 1
ORDER BY share_suppressed DESC;
```
