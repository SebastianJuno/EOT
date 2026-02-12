PYTHON ?= python3.12
PYTHON_MAJOR_MINOR ?= 3.12
VENV ?= .venv
VENV_PY ?= $(VENV)/bin/python

.PHONY: setup test run run-open run-desktop-dev package-macos install-local-app open-local-app build-parser check-python check-venv clean-venv bootstrap-macos

check-python:
	@command -v $(PYTHON) >/dev/null || (echo "ERROR: $(PYTHON) not found. Install Python 3.12 first."; exit 1)

check-venv:
	@[ -x "$(VENV_PY)" ] || (echo "ERROR: $(VENV) missing. Run 'make setup'."; exit 1)
	@$(VENV_PY) -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3,12) else 1)' || \
	(echo "ERROR: $(VENV) uses Python < 3.12. Run 'make setup' to rebuild it."; exit 1)

clean-venv:
	rm -rf $(VENV)

setup: check-python
	@if [ -x "$(VENV_PY)" ]; then \
		$(VENV_PY) -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3,12) else 1)' || \
		( echo "Detected old virtualenv (<3.12). Rebuilding $(VENV)..."; rm -rf $(VENV) ); \
	fi
	$(PYTHON) -m venv $(VENV)
	. $(VENV)/bin/activate && pip install --upgrade pip && pip install -r requirements.txt

build-parser:
	cd java-parser && mvn clean package

test: check-venv
	. $(VENV)/bin/activate && pytest -q

run: check-venv
	. $(VENV)/bin/activate && uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000

run-open: check-venv
	./scripts/run_and_open_macos.sh

run-desktop-dev: check-venv
	. $(VENV)/bin/activate && pip install -r requirements-desktop.txt && python -m desktop.main

package-macos: check-venv
	./scripts/build_macos_app.sh

install-local-app: check-venv
	./scripts/install_local_repo_app.sh

open-local-app:
	open "local-app/EOT Diff Tool.app"

bootstrap-macos:
	./scripts/bootstrap_macos.sh
