# Releases

MaSoVa Support is a deployable service. Releases use **Semantic Versioning**
and immutable Git tags. Do not invent ad-hoc tag names.

## Version

Format: `vMAJOR.MINOR.PATCH` (example: `v0.4.0`).

| Increment | When |
|-----------|------|
| **PATCH** | Backward-compatible bug fixes, security fixes, docs-only releases when a release is warranted |
| **MINOR** | Backward-compatible new functionality |
| **MAJOR** | Breaking changes for callers of the HTTP API or documented contracts |

Before **v1.0.0**, treat changes as potentially breaking unless a changelog
entry says otherwise. Do not declare v1.0.0 until the service is the intended
stable public milestone.

Package version in `pyproject.toml` must match the Git tag (without the `v`
prefix) and the GitHub Release.

Do not reuse a published version. Do not move or delete a published tag.

## Current status

Changelog documents historical versions **0.1.0**, **0.3.0**, and **0.4.0**.
Those versions were **not** tagged in Git. Do not backfill tags onto guessed
commits. The next production cut should be tagged from `main` after CI is green
(likely `v0.5.0` if Unreleased work is the first tagged ship, or `v0.4.0` only
if that cut is intentionally the first tag and matches that changelog section).

## Process

1. Working tree clean; branch is up-to-date `main`.
2. Required CI check `test` is green (hygiene, flake8 syntax, import, pytest, pip-audit).
3. Choose the SemVer increment from the table above.
4. Update `pyproject.toml` `[project].version`.
5. Move `[Unreleased]` notes in `CHANGELOG.md` under the new version and date.
   Use Added / Changed / Fixed / Removed / Deprecated / Security. Do not
   fabricate history.
6. Commit: `chore(release): vX.Y.Z`
7. Annotated tag: `git tag -a vX.Y.Z -m "Release vX.Y.Z"`
8. Push commit and tag: `git push origin main && git push origin vX.Y.Z`
9. Create a GitHub Release **from that tag** (title `vX.Y.Z`), with the
   changelog notes. Mark prerelease only for real prereleases
   (`v2.0.0-rc.1`, not `final-final`).
10. Confirm tag, GitHub Release, and `pyproject.toml` version all match.

No second human reviewer is required. Self-review plus green CI is the bar.

## Rollback

Never retarget an existing tag. Fix on `main`, then release a new version
(for example `v1.4.0` buggy → `v1.4.1`).

## Prereleases

Use SemVer identifiers only: `v2.0.0-alpha.1`, `v2.0.0-beta.1`, `v2.0.0-rc.1`.

## Release branches

Not used. Flow is: short-lived branch → PR → `main` → tag.
