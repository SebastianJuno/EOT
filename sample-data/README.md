# Complex V30 Sample Dataset

Deterministic construction scenario with mixed hierarchy, concurrency, and typed dependencies.

## Files

- Canonical scenario source: `scenario-complex-v30.json`
- Generator script: `generate_complex_samples.py`
- Microsoft Project XML outputs:
  - `programme-v1.xml`
  - `programme-v2.xml`
- Asta-style CSV outputs:
  - `asta-export-v1.csv`
  - `asta-export-v2.csv`
- Successor derivation artifact:
  - `successor-matrix.md`

## Scenario shape

- 30 rows in V1 and 30 rows in V2.
- Per version: 6 summary tasks + 24 leaf tasks.
- Shared descriptions across versions: 27.
- Removed from V1: 3.
- Added in V2: 3.
- Shared split: 18 unchanged, 9 changed (computed from canonical task signatures).

The scenario includes parallel workstreams and mixed relationship labels in predecessor links:
`FS`, `SS`, `FF`, `SF`.

## Notes on compare behavior

The current compare pipeline matches by description and compares predecessor UID lists directly.
Because V2 uses a renumbered UID range, predecessor evidence will often be flagged as changed even for logically equivalent chains. This dataset intentionally keeps those typed relationships in-source for realism while remaining parse-compatible with existing `/api/compare-auto`.

## Regenerate outputs

From the repository root:

```bash
python3 sample-data/generate_complex_samples.py
```

Or with Make:

```bash
make generate-sample-data
```

Generation is idempotent and deterministic (stable ordering and formatting).

## Successor matrix

`successor-matrix.md` is generated from predecessor links in the canonical JSON.
It shows predecessor and successor visibility for each task so the dependency network can be inspected without manual graph reconstruction.

## `.mpp` conversion path

No `.mpp` binaries are committed in this repository.

To produce `.mpp` files for manual compare testing:

1. Open `programme-v1.xml` in Microsoft Project (or Project Plan 365).
2. Save as `programme-v1.mpp`.
3. Open `programme-v2.xml`.
4. Save as `programme-v2.mpp`.
5. Upload the `.mpp` pair in the app for direct `.mpp` compare.

## `.pp` support note

Direct `.pp` parsing remains unsupported in this task.
Use exported CSV (`asta-export-v1.csv`, `asta-export-v2.csv`) as the fallback workflow.
