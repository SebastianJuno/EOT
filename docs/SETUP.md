# Setup and Distribution (macOS)

## Goal

Build a desktop `.app` your colleagues can launch from Finder without terminal usage.

## Step 1: Prepare build machine

```bash
cd ~/Documents/<project-folder>
make bootstrap-macos
```

## Step 2: Build and install a local app in this repository

```bash
cd ~/Documents/<project-folder>
make install-local-app
```

Expected local app:
- `local-app/EOT Diff Tool.app`

Open it with:

```bash
make open-local-app
```

Or double-click:
- `local-app/EOT Diff Tool.app`
- `Run EOT Diff Tool.command`

## Step 3: Build zipped share artifact

```bash
cd ~/Documents/<project-folder>
make package-macos
```

Expected output:
- `dist/EOT Diff Tool.app`
- `dist/EOT-Diff-Tool-mac-universal.zip`

## Step 4: Share with colleagues

Share:
- `dist/EOT-Diff-Tool-mac-universal.zip`

Colleague steps:
1. Unzip.
2. Double-click `EOT Diff Tool.app`.
3. If blocked by Gatekeeper (unsigned internal build): right-click -> `Open`.

## Runtime behavior on colleague machine

On launch, app will:
1. Check Java 17 runtime.
2. If missing, prompt to install prerequisites.
3. If auto-install fails, show manual fix instructions and offer one-click Java 17 download page.
4. Start backend locally.
5. Open UI in a native window.
6. Stop backend automatically when app closes.

## Troubleshooting

- App opens but compare fails on `.mpp`:
  - Java may be missing. Relaunch app and allow install prompt.
  - If auto-install fails, use the in-app "Open Download Page" button and install Java 17 manually.
- Packaging fails on PyInstaller arch:
  - Ensure Python build env supports universal2 target.
- Need logs:
  - `~/Library/Logs/EOTDiff/launcher.log`
