ROOT_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
PYTHON ?= python3.12
VENV ?= $(ROOT_DIR)/.venv
VENV_PY ?= $(VENV)/bin/python

.PHONY: setup test run run-open run-desktop-dev package-macos install-local-app open-local-app build-parser check-python check-venv clean-venv bootstrap-macos generate-sample-data

check-python:
	@command -v $(PYTHON) >/dev/null || (echo "ERROR: $(PYTHON) not found. Install Python 3.12 first."; exit 1)

check-venv:
	@[ -x "$(VENV_PY)" ] || (echo "ERROR: $(VENV) missing. Run 'make -f scripts/Makefile setup'."; exit 1)
	@"$(VENV_PY)" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3,12) else 1)' || \
	(echo "ERROR: $(VENV) uses Python < 3.12. Run 'make -f scripts/Makefile setup' to rebuild it."; exit 1)

clean-venv:
	rm -rf "$(VENV)"

setup: check-python
	@if [ -x "$(VENV_PY)" ]; then \
		"$(VENV_PY)" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3,12) else 1)' || \
		( echo "Detected old virtualenv (<3.12). Rebuilding $(VENV)..."; rm -rf "$(VENV)" ); \
	fi
	$(PYTHON) -m venv "$(VENV)"
	. "$(VENV)/bin/activate" && pip install --upgrade pip && pip install -r "$(ROOT_DIR)/backend/requirements.txt"

build-parser:
	cd "$(ROOT_DIR)/java-parser" && mvn -DskipTests -Dmaven.test.skip=true clean package

test: check-venv
	cd "$(ROOT_DIR)" && . "$(VENV)/bin/activate" && pytest -q

run: check-venv
	cd "$(ROOT_DIR)" && . "$(VENV)/bin/activate" && uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000

run-open: check-venv
	cd "$(ROOT_DIR)" && ./scripts/run_and_open_macos.sh

run-desktop-dev: check-venv
	cd "$(ROOT_DIR)" && . "$(VENV)/bin/activate" && pip install -r desktop/requirements.txt && python -m desktop.main

package-macos: check-venv
	cd "$(ROOT_DIR)" && ./scripts/build_macos_app.sh

install-local-app: check-venv
	cd "$(ROOT_DIR)" && ./scripts/install_local_repo_app.sh

open-local-app:
	cd "$(ROOT_DIR)" && open "EOT Diff Tool.app"

bootstrap-macos:
	cd "$(ROOT_DIR)" && ./scripts/bootstrap_macos.sh

generate-sample-data:
	cd "$(ROOT_DIR)" && $(PYTHON) sample-data/generate_complex_samples.py
