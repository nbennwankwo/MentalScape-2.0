# Short commands for everyday tasks. Run  make help  to list them.

PY := uv run

.PHONY: help setup lint format test profile changelog check

help:
	@echo "setup      create the environment and install git hooks"
	@echo "lint       run the linter"
	@echo "format     format the code"
	@echo "test       run the tests"
	@echo "profile    profile every MHSDS monthly file in data/raw/mhsds_monthly"
	@echo "changelog  rebuild the MHSDS change log from the profiles"
	@echo "check      lint and test, the same checks as CI"

setup:
	uv sync --extra dev
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
