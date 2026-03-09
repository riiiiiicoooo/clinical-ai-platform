.PHONY: dev test lint setup migrate

dev:
	docker-compose up -d postgres redis
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest tests/ -v --tb=short

lint:
	ruff check src/
	mypy src/ --ignore-missing-imports

setup:
	pip install -r requirements.txt
	python -m spacy download en_core_sci_sm

migrate:
	psql $(DATABASE_URL) -f schema/001_core_tables.sql
	psql $(DATABASE_URL) -f schema/002_prior_auth_tables.sql
	psql $(DATABASE_URL) -f schema/003_coding_tables.sql
	psql $(DATABASE_URL) -f schema/004_compliance_tables.sql
	psql $(DATABASE_URL) -f schema/005_rls_policies.sql

eval:
	python -m evals.run_evals
