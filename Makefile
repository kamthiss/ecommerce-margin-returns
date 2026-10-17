PY := .venv/bin/python

.PHONY: setup all notebook reset-db down

setup:
	uv venv --managed-python --python 3.12 --allow-existing .venv
	uv pip install --python $(PY) -r requirements.txt

all:
	$(PY) src/generate.py
	docker compose up -d --wait
	$(PY) src/load_raw.py
	cd dbt && ../.venv/bin/dbt build --profiles-dir .
	$(PY) src/metabase_setup.py

notebook:
	.venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/margin_analysis.ipynb

reset-db:
	docker compose down -v
	$(MAKE) all

down:
	docker compose down
