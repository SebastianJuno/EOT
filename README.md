# EOT Programme Diff Tool (v1)

Offline, single-user app for comparing programme versions for delay/claims preparation.

## What this now supports

- Native macOS desktop launcher (`.app`) for no-terminal usage by colleagues.
- Auto prerequisite checks on app launch (Java 17 required for `.mpp`).
- Auto backend startup + native window UI + clean shutdown on close.
- Auto file type detection by extension (`.mpp`, `.xml`, `.csv`).
- Mixed file type uploads blocked with clear errors.
- `.pp` direct upload blocked with CSV export guidance.
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
- macOS build script: `scripts/build_macos_app.sh`
- Local app installer script: `scripts/install_local_repo_app.sh`
- Runtime logs: `~/Library/Logs/EOTDiff/launcher.log`
- Runtime config: `~/Library/Application Support/EOTDiff/config.json`

## Existing web/API features preserved

- Compare API: `/api/compare-auto`
- Attribution API: `/api/attribution/apply`
- Exports: `/api/export/csv`, `/api/export/pdf`
- SCL-aligned attribution and fault allocation outputs remain unchanged.
# EOT
