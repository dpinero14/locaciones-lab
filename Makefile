PY ?= python
VENV ?= .venv
BIN := $(VENV)/bin
ifeq ($(OS),Windows_NT)
BIN := $(VENV)/Scripts
endif

.PHONY: setup test data notebooks

setup:
	$(PY) -m venv $(VENV)
	$(BIN)/python -m pip install --upgrade pip
	$(BIN)/python -m pip install -r requirements.txt
	$(BIN)/python -m ipykernel install --user --name locaciones-lab --display-name "locaciones-lab"

test:
	$(BIN)/python -m pytest -q tests

data:
	$(BIN)/python scripts/download_data.py --series

notebooks:
	$(BIN)/python -m jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.kernel_name=locaciones-lab --ExecutePreprocessor.timeout=7200 notebooks/01_la_locacion_se_ve.ipynb
	$(BIN)/python -m jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.kernel_name=locaciones-lab --ExecutePreprocessor.timeout=7200 notebooks/02_el_detector_a_ciegas.ipynb
	$(BIN)/python -m jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.kernel_name=locaciones-lab --ExecutePreprocessor.timeout=7200 notebooks/03_las_antorchas.ipynb
	$(BIN)/python -m jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.kernel_name=locaciones-lab --ExecutePreprocessor.timeout=7200 notebooks/04_el_clasificador.ipynb
