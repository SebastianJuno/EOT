# Changelog

All notable changes to this project should be documented in this file.

The format is based on Keep a Changelog and this project uses Semantic Versioning.

## [Unreleased]

### Added
- Placeholder for upcoming features.

### Changed
- Placeholder for upcoming behavior changes.

### Fixed
- Placeholder for upcoming bug fixes.

## [0.1.0] - 2026-02-12

### Added
- Native desktop launcher architecture under `desktop/`.
- Auto file-type detection for uploads (`.mpp`, `.xml`, `.csv`) with mixed-type blocking.
- `.pp` direct-upload rejection with CSV fallback guidance.
- SCL-aligned attribution workflow:
  - cause tags (`client`, `contractor`, `neutral`, `unassigned`)
  - reason codes
  - inline and bulk assignment
  - low-confidence exclusion flow
- Fault allocation metrics and summaries:
  - project finish impact days
  - task slippage days
- Extended CSV and PDF exports with attribution and fault summary.
- Single-server run mode (backend serves frontend).
- Bootstrap tooling for macOS dependency setup.
- Packaging scripts for native app bundle and zip distribution.
- Local repository app installer and launcher.

### Changed
- App launch flow simplified for internal testing and colleague distribution.
- Makefile targets expanded for setup, desktop run, packaging, and local app install.

### Fixed
- Python version guardrails to avoid venv/runtime mismatch issues.

[Unreleased]: https://example.invalid/compare/v0.1.0...HEAD
[0.1.0]: https://example.invalid/releases/tag/v0.1.0
