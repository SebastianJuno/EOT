# Changelog

All notable changes to this project should be documented in this file.

The format is based on Keep a Changelog and this project uses Semantic Versioning.

## [Unreleased]

### Added
- None yet.

### Changed
- Reorganized repository root so only `README.md`, `CHANGELOG.md`, and `EOT Diff Tool.app` remain as top-level non-hidden entries.
- Moved release metadata to `config/VERSION`, developer make targets to `scripts/Makefile`, and Python requirements files into `backend/requirements.txt` and `desktop/requirements.txt`.
- Updated scripts and docs to use `make -f scripts/Makefile ...` with the new folder structure.

### Fixed
- None yet.

## [0.1.0] - 2026-02-12

### Added
- API compare pipeline for `.mpp`, `.xml`, and `.csv` inputs via `/api/compare-auto`.
- Automatic file-kind detection with mixed-type blocking and explicit `.pp` rejection guidance.
- Matching and comparison evidence across dates, duration, progress, and predecessor chains.
- SCL-style attribution model with cause tags, reason codes, inline assignment, and bulk assignment.
- Fault allocation summary output including delay impact and per-party rollups.
- Export endpoints for evidence pack CSV and PDF outputs.
- Preview workflow endpoints: `/api/preview/init`, `/api/preview/rows`, `/api/preview/matches/apply`, `/api/preview/analyze`.
- Preview session management with TTL cleanup, row paging, timeline bounds, and manual match override support.
- Java parser bridge for `.mpp` extraction with surfaced parser errors.
- Frontend static hosting from backend for single-process local execution.
- macOS desktop launcher with backend lifecycle management and native webview shell.
- Desktop prerequisite checks with Java 17 validation, logs, and guided remediation flow.
- macOS helper scripts for bootstrap, local app install/open, and packaged distribution.
- Deterministic complex sample-data scenario (30 rows/version, mixed hierarchy, typed dependencies) with generator script.
- Successor matrix artifact generated from predecessor links for traceable dependency visibility.
- Sample-data integrity tests covering counts, matrix constraints, overlap concurrency, dependency acyclicity, summary envelopes, and compare compatibility.
- Single `VERSION` file (`/VERSION`) as the release version source for backend and desktop packaging metadata.

### Changed
- Desktop launch flow hardened with failure handling and UI lock safety controls.
- Local developer workflow expanded via Makefile targets for setup, run, test, packaging, parser build, and sample-data regeneration.
- Packaging now injects app bundle version from `/VERSION` during PyInstaller build.
- Sample-data documentation expanded with regeneration commands and `.mpp` conversion path from XML.

### Fixed
- Python version guardrails to avoid venv/runtime mismatch issues.
- Upload validation messages improved for unsupported or missing file extensions.
- Preview and compare error paths normalized to JSON error responses.

[Unreleased]: https://example.invalid/compare/v0.1.0...HEAD
[0.1.0]: https://example.invalid/releases/tag/v0.1.0
