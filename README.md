# EOT Programme Diff Tool (v1)

Offline, single-user app for comparing programme versions for delay/claims preparation.

## What this now supports

- Native macOS desktop launcher (`.app`) for no-terminal usage by colleagues.
- Auto prerequisite checks on app launch (Java 17 required for `.mpp`).
- Auto backend startup + native window UI + clean shutdown on close.
- Auto file type detection by extension (`.mpp`, `.xml`, `.csv`).
- Mixed file type uploads blocked with clear errors.
- `.pp` direct upload blocked with CSV export guidance.
- Actionable-first comparison UX: only rows requiring explanation are shown by default.
- Automatic no-action classification for certain identity matches (`UID + normalized name + duration`) with optional manual override.
- Propagation-aware date drift handling that auto-tags downstream flow-on shifts while keeping ambiguous cases actionable.
- Flexible CSV column inference (header + value-shape scoring) so non-standard export schemas can be parsed without strict column-name matches.
- Synthetic UID fallback for CSVs without reliable UID columns, with clear import warnings and certainty-safe matching behavior.
- MSP-style textual duration parsing for CSV values such as `88w 1d`, `33w 4h`, and `13w 2.5d`.
- If auto prerequisite install fails, app shows manual fix instructions and a one-click Java 17 download link.

## Quick start (developer machine)

1. Bootstrap tools:

```bash
cd ~/Documents/<project-folder>
make -f scripts/Makefile bootstrap-macos
```

2. Build app and install a local `.app` inside the repository:

```bash
make -f scripts/Makefile install-local-app
```

3. Open local app:

```bash
make -f scripts/Makefile open-local-app
```

Or double-click:

- `EOT Diff Tool.app`
- `scripts/Run EOT Diff Tool.command`

## Shareable artifact

Build zipped artifact:

```bash
make -f scripts/Makefile package-macos
```

Output:

- `dist/EOT-Diff-Tool-mac-universal.zip`

## Colleague launch flow

1. Unzip `EOT-Diff-Tool-mac-universal.zip`.
2. Open `EOT Diff Tool.app` from Finder.
3. If Gatekeeper warns (unsigned internal app): right-click app -> `Open`.
4. App checks prerequisites, starts backend automatically, and opens UI in native window.

## Build/packaging internals

- Desktop launcher code: `desktop/`
- PyInstaller spec: `desktop/pyinstaller.spec`
- Packaging mode: onedir app bundle (optimized for faster cold startup splash display)
- macOS build script: `scripts/build_macos_app.sh`
- Local app installer script: `scripts/install_local_repo_app.sh`
- Runtime logs: `~/Library/Logs/EOTDiff/launcher.log`
- Runtime config: `~/Library/Application Support/EOTDiff/config.json`

## Performance regression checks

Generate a benchmark report:

```bash
make -f scripts/Makefile perf-audit
```

Detect regressions against the repo baseline (`config/perf-baseline.json`):

```bash
make -f scripts/Makefile perf-check
```

Latest report output:

- `build/perf-latest.json`

Startup splash timing check (latest launch, pass/fail against 500ms target):

```bash
make -f scripts/Makefile startup-timing
```

## Existing web/API features preserved

- Compare API: `/api/compare-auto`
- Attribution API: `/api/attribution/apply`
- Exports: `/api/export/csv`, `/api/export/pdf`
- SCL-aligned attribution and fault allocation outputs remain unchanged.
# EOT
