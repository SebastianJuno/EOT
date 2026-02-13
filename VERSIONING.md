# Versioning and Release Process

## Version format

Use Semantic Versioning:

- `MAJOR.MINOR.PATCH`
- Example: `0.1.0`

Rules:

- `PATCH` (`0.1.1`): bug fixes only, no breaking behavior.
- `MINOR` (`0.2.0`): new features, backwards-compatible behavior.
- `MAJOR` (`1.0.0`): breaking changes or major product milestone.

## Single source of truth

- Repo release version is stored in `/VERSION`.
- Use plain semantic version without prefix (example: `0.1.0`).
- Backend API version and desktop bundle version are derived from `/VERSION`.

## Branch strategy

- `main`: stable code suitable for internal release builds.
- `codex/feature-*`: feature work branches.
- `codex/release-vX.Y.Z`: release prep branch (optional but recommended).

## Commit convention (recommended)

Use short prefixes for clarity:

- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation
- `build:` packaging/build system
- `refactor:` non-functional code cleanup
- `test:` test changes

Examples:

- `feat: add desktop prereq wizard for Java 17`
- `fix: reject mixed upload extensions in auto-compare`

## Release checklist

1. Update `CHANGELOG.md`:
- move items from `Unreleased` into new version section.
- add release date.

2. Set release version in `/VERSION`:

```bash
echo "X.Y.Z" > VERSION
```

3. Verify app behavior:

```bash
cd ~/Documents/<project-folder>
make setup
make build-parser
make test
make package-macos
```

4. Commit release changes:

```bash
git add .
git commit -m "release: vX.Y.Z"
```

5. Tag release:

```bash
git tag -a vX.Y.Z -m "Release vX.Y.Z"
```

6. Push branch and tags:

```bash
git push origin HEAD
git push origin --tags
```

7. Publish/share artifact:

- `dist/EOT-Diff-Tool-mac-universal.zip`

## Hotfix process

For urgent production/internal pilot fixes:

1. Branch from latest stable tag:

```bash
git checkout -b codex/hotfix-vX.Y.(Z+1) vX.Y.Z
```

2. Apply minimal fix and test.
3. Tag as next patch version.
4. Merge back into `main`.

## Tagging policy

- Always tag release commits as `vX.Y.Z`.
- Do not reuse or move existing tags.
- Keep annotated tags (`-a`) for release notes.

## Artifact naming policy

Use predictable names:

- `EOT-Diff-Tool-mac-universal.zip`

Optionally include version when archiving externally:

- `EOT-Diff-Tool-v0.1.0-mac-universal.zip`
