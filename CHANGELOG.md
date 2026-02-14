# Changelog

All notable changes to this project should be documented in this file.

The format is based on Keep a Changelog and this project uses Semantic Versioning.

## [Unreleased]

### Added
- None yet.

### Changed
- None yet.

### Fixed
- None yet.

## [0.1.1] - 2026-02-14

### Added
- Deterministic performance benchmark harness at `scripts/perf_bench.py` covering compare and preview hot paths.
- Repository baseline benchmark file at `config/perf-baseline.json` and report output path `build/perf-latest.json`.
- Background progress-job framework at `backend/progress_jobs.py` with in-memory lifecycle tracking (`queued`, `running`, `completed`, `failed`), TTL cleanup, and capped retention.
- Additive progress APIs: `POST /api/progress/compare-auto`, `POST /api/progress/preview/init`, `POST /api/progress/preview/analyze`, and `GET /api/progress/jobs/{job_id}`.
- Coverage for progress APIs and desktop splash startup flow in `tests/test_progress_jobs.py` and expanded `tests/test_desktop_main.py`.

### Changed
- Reorganized repository root so only `README.md`, `CHANGELOG.md`, and `EOT Diff Tool.app` remain as top-level non-hidden entries.
- Moved release metadata to `config/VERSION`, developer make targets to `scripts/Makefile`, and Python requirements files into `backend/requirements.txt` and `desktop/requirements.txt`.
- Updated scripts and docs to use `make -f scripts/Makefile ...` with the new folder structure.
- Added `make -f scripts/Makefile perf-audit` (report) and `perf-check` (threshold-enforced regression check) developer targets.
- Optimized matching and comparison paths to reduce worst-case fallback matching cost and remove repeated candidate lookup scans.
- Cached preview session leaf/summary partitions to avoid repeated filtering during row builds.
- Frontend compare/analysis actions now use job-based progress polling with a full-screen minimalist loading overlay that appears immediately and updates through backend stages.
- Desktop startup now uses an immediate pywebview splash progress screen and transitions the same window into the main app URL after backend health succeeds, with fallback to dialog mode on splash failure.
- Backend compare/preview orchestration refactored into reusable operation helpers that optionally emit progress updates while preserving existing synchronous endpoints.

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

[Unreleased]: https://example.invalid/compare/v0.1.1...HEAD
[0.1.1]: https://example.invalid/compare/v0.1.0...v0.1.1
[0.1.0]: https://example.invalid/releases/tag/v0.1.0
