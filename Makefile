ANOS ?= 2020 2021 2022 2023 2024 2025 2026
DB_DEMO := $(CURDIR)/data/warehouse/demo.duckdb

.PHONY: instalar testes lint baixar ingerir transformar pipeline dashboard demo dashboard-demo limpar

instalar:
	pip install -e ".[transformacao,dashboard,dev]"

testes:
	pytest -q

lint:
	ruff check src tests dashboard scripts

baixar:
	python -m inmet_pipeline baixar --anos $(ANOS)

ingerir:
	python -m inmet_pipeline ingerir --anos $(ANOS)

transformar:
	cd dbt && dbt build --profiles-dir .

## Pipeline completo com dados reais do INMET (os ZIPs anuais são grandes; o download
## acontece só na primeira vez, depois fica em cache em data/raw).
pipeline: baixar ingerir transformar

dashboard:
	streamlit run dashboard/app.py

## Pipeline com os dados de exemplo de tests/fixtures (não precisa de internet).
demo:
	rm -f $(DB_DEMO)
	INMET_DB_PATH=$(DB_DEMO) python -m inmet_pipeline ingerir --pasta tests/fixtures
	cd dbt && INMET_DB_PATH=$(DB_DEMO) dbt build --profiles-dir .

dashboard-demo:
	INMET_DB_PATH=$(DB_DEMO) streamlit run dashboard/app.py

limpar:
	rm -rf dbt/target dbt/logs data/warehouse .pytest_cache