# Short commands for everyday tasks. Run  make help  to list them.

PY := uv run

.PHONY: help setup lint format test profile changelog check catalogue fetch warehouse warehouse-fixture

help:
	@echo "setup      create the environment and install git hooks"
	@echo "lint       run the linter"
	@echo "format     format the code"
	@echo "test       run the tests"
	@echo "profile    profile every MHSDS monthly file in data/raw/mhsds_monthly"
	@echo "changelog  rebuild the MHSDS change log from the profiles"
	@echo "check      lint and test, the same checks as CI"
	@echo "catalogue  rebuild the catalogue from a browser card list, CARDS=path/to/mhsds_cards.json"
	@echo "fetch      download the preferred monthly files from the data release"
	@echo "warehouse  fetch, load and build the full warehouse in DuckDB"
	@echo "warehouse-fixture  build the warehouse from the small synthetic fixture"

setup:
	uv sync --extra dev --extra warehouse
	$(PY) pre-commit install

lint:
	$(PY) ruff check src tests

format:
	$(PY) ruff format src tests

test:
	$(PY) pytest

profile:
	$(PY) python -m mentalscape.profiling.mhsds_release_profile data/raw/mhsds_monthly --out data/interim/profiles

changelog:
	$(PY) python -m mentalscape.profiling.mhsds_change_log

check: lint test

catalogue:
	$(PY) python -m mentalscape.ingest.mhsds classify --cards $(CARDS)

fetch:
	$(PY) python -m mentalscape.warehouse.fetch --dest data/raw/release

DBT := $(PY) dbt build --project-dir warehouse --profiles-dir warehouse

warehouse: fetch
	$(PY) python -m mentalscape.warehouse.load --manifest data/raw/release/manifest.csv --assets data/raw/release
	$(DBT) --target local

warehouse-fixture:
	$(PY) python -m mentalscape.warehouse.fixture --out data/interim/fixture
	$(PY) python -m mentalscape.warehouse.load --manifest data/interim/fixture/manifest.csv \
		--assets data/interim/fixture/assets --duckdb-path data/warehouse/fixture.duckdb
	MENTALSCAPE_DUCKDB=data/warehouse/fixture.duckdb $(DBT) --target local --vars '{min_sub_icbs_per_release: 2}'
