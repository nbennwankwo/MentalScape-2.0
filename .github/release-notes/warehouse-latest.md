The latest full build of the MentalScape 2.0 warehouse, replaced by the `Build warehouse` workflow after every new release and every Saturday (docs/adr/0013).

- `mentalscape.duckdb.zst` is the whole warehouse as one DuckDB file, compressed with zstd. Decompress it with `zstd -d mentalscape.duckdb.zst` and open it with DuckDB from Python, the DuckDB command line or a tool such as DBeaver. The tables to use are in the `marts` schema.
- `build_summary.md` lists what each source covers, the size of every table and any warnings from the data tests.
- `run_results.json` is dbt's own record of every model and test in the build.

The warehouse holds only published aggregate statistics, the same as the raw data releases. It contains public sector information licensed under the Open Government Licence v3.0 from NHS England, the Office for National Statistics and the Ministry of Housing, Communities and Local Government, and Ordnance Survey data, Crown copyright and database right.
