PYTHON?=python3
VENV?=.venv

.PHONY: venv lint test run-test run-camera build-deb

venv:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -e .[dev]

lint:
	$(VENV)/bin/ruff check src tests

test:
	$(VENV)/bin/pytest -q

run-test:
	$(VENV)/bin/scale-vision run --config samples/sample_config_test.json

run-camera:
	$(VENV)/bin/scale-vision run --config samples/sample_config_camera.json

build-deb:
	bash scripts/build_deb.sh
