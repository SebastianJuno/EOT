# Test schedules

Microsoft Project XML pair:
- `programme-v1.xml`
- `programme-v2.xml`

Asta export CSV pair (for `.pp` fallback workflow):
- `asta-export-v1.csv`
- `asta-export-v2.csv`

## What differences are included

- task ID/UID renumbering
- inserted new task (`Site investigation`)
- removed task (`Commissioning` from v1)
- changed start/finish/duration on matching tasks
- changed predecessor links
- changed percent complete
- baseline variance differences

## Use XML directly

You can now upload the XML files directly in app mode: `Direct .xml compare`.

## Optional: convert XML to `.mpp`

1. Open each XML in Microsoft Project (or Project Plan 365).
2. Save As `programme-v1.mpp` and `programme-v2.mpp`.

## `.pp` fallback test

If you do not have a direct `.pp` parser SDK:

1. Export each Asta programme to CSV.
2. In the web app, choose `Asta export CSV fallback` mode.
3. Upload both CSV files.
4. Confirm column mappings and compare.
