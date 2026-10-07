# Makefile for the Loblaw Bio cell-count analysis.
#
#   make            install dependencies, then run the full pipeline
#   make setup      install the Python packages in requirements.txt
#   make pipeline   build the database and run the analysis (Parts 1-4)
#   make dashboard  start the interactive dashboard (Parts 2-4 results)

PYTHON ?= python3

.DEFAULT_GOAL := all
.PHONY: all setup pipeline dashboard clean

all: setup pipeline

setup:
	$(PYTHON) -m pip install -r requirements.txt

pipeline:
	$(PYTHON) load_data.py
	$(PYTHON) analysis.py

dashboard:
	@test -f cell_counts.db || { echo "cell_counts.db not found. Run 'make pipeline' first."; exit 1; }
	$(PYTHON) dashboard.py

clean:
	rm -rf cell_counts.db outputs __pycache__
