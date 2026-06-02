.PHONY: install test build build-offline clean

install:
	python -m pip install -r requirements.txt

test:
	python -m pytest -q

build:
	python scripts/build_index.py --config config/sources.yml

build-offline:
	python scripts/build_index.py --config config/sources.yml --offline

clean:
	rm -rf public .pytest_cache **/__pycache__
