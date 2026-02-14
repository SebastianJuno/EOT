# Setup and Distribution (macOS)

## Goal

Build a desktop `.app` your colleagues can launch from Finder without terminal usage.

## Step 1: Prepare build machine

```bash
cd ~/Documents/<project-folder>
make -f scripts/Makefile bootstrap-macos
```

## Step 2: Build and install a local app in this repository

```bash
cd ~/Documents/<project-folder>
make -f scripts/Makefile install-local-app
```

Expected local app:
- `EOT Diff Tool.app`

Open it with:

```bash
make -f scripts/Makefile open-local-app
```

Or double-click:
- `EOT Diff Tool.app`
- `scripts/Run EOT Diff Tool.command`

## Step 3: Build zipped share artifact

```bash
cd ~/Documents/<project-folder>
make -f scripts/Makefile package-macos
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

## Startup timing check

After launching the desktop app at least once, you can read the latest splash timing from launcher logs:

```bash
cd ~/Documents/<project-folder>
make -f scripts/Makefile startup-timing
```

## Troubleshooting

- App opens but compare fails on `.mpp`:
  - Java may be missing. Relaunch app and allow install prompt.
  - If auto-install fails, use the in-app "Open Download Page" button and install Java 17 manually.
- Packaging fails on PyInstaller arch:
  - Ensure Python build env supports universal2 target.
- Need logs:
  - `~/Library/Logs/EOTDiff/launcher.log`
