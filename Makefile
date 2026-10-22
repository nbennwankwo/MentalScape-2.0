# Short commands for everyday tasks. Run  make help  to list them.

PY := uv run

.PHONY: help setup lint format test profile changelog check catalogue catalogue-tt fetch warehouse warehouse-fixture summary

help:
	@echo "setup      create the environment and install git hooks"
	@echo "lint       run the linter"
	@echo "format     format the code"
	@echo "test       run the tests"
	@echo "profile    profile every MHSDS monthly file in data/raw/mhsds_monthly"
	@echo "changelog  rebuild the MHSDS change log from the profiles"
	@echo "check      lint and test, the same checks as CI"
	@echo "catalogue  rebuild the MHSDS catalogue from a browser card list, CARDS=path/to/mhsds_cards.json"
	@echo "catalogue-tt  rebuild the Talking Therapies catalogue, CARDS=path/to/talking_therapies_cards.json"
	@echo "fetch      download every source from the data releases, checking checksums"
	@echo "warehouse  fetch, load and build the full warehouse in DuckDB"
	@echo "warehouse-fixture  build the warehouse from the small synthetic fixture"
	@echo "summary    write build_summary.md for the last warehouse build"

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

catalogue-tt:
	$(PY) python -m mentalscape.ingest.talking_therapies classify --cards $(CARDS)

fetch:
	$(PY) python -m mentalscape.warehouse.fetch --source all --raw-dir data/raw

DBT := $(PY) dbt build --project-dir warehouse --profiles-dir warehouse

warehouse: fetch
	$(PY) python -m mentalscape.warehouse.load --source all --raw-dir data/raw
	$(DBT) --target local

warehouse-fixture:
	$(PY) python -m mentalscape.warehouse.fixture --out data/interim/fixture
	$(PY) python -m mentalscape.warehouse.load --source all --raw-dir data/interim/fixture \
		--duckdb-path data/warehouse/fixture.duckdb
	MENTALSCAPE_DUCKDB=data/warehouse/fixture.duckdb $(DBT) --target local --vars '{min_sub_icbs_per_release: 2}'

summary:
	$(PY) python -m mentalscape.warehouse.summary --out build_summary.md
