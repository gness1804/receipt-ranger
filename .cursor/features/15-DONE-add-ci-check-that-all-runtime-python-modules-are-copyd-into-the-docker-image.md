---
github_issue: 87
---
# Add CI check that all runtime Python modules are COPYd into the Docker image

## Working directory

`~/Desktop/receipt-ranger`

## Contents

## Working directory

`~/Desktop/receipt-ranger`

## Contents

## Summary

Add a CI check (and/or a pre-commit check) that fails when a tracked top-level
Python module in the repo root is **not** `COPY`'d into the Docker image. This
prevents a recurring class of production outage where a new runtime module is
added and imported but never copied into the container, so the app crashes at
startup with `ModuleNotFoundError`.

## Motivation

This has now broken production **twice**, same root cause both times:

- Issue #60 — `validation/` was imported by `main.py` but missing from the
  Dockerfile (caught during the Render migration).
- Issue #85-era HEIC work — `image_conversion.py` was imported by `main.py`
  and `app.py` but missing from the Dockerfile, taking the live site down with
  `ModuleNotFoundError: No module named 'image_conversion'` (fixed by the
  `hotfix/dockerfile-image-conversion` branch).

Local dev and `pytest` both pass in these cases because the file exists in the
repo — only the *container build* omits it. So nothing catches it before
deploy. A cheap automated check would close that gap.

## Proposed approach

A small script (e.g. `scripts/check_dockerfile_copies.py`) that:

1. Enumerates tracked top-level `*.py` modules in the repo root
   (`git ls-files '*.py'` filtered to no `/` in the path).
2. Parses the `Dockerfile` for `COPY <name>.py` lines.
3. Fails (non-zero exit) listing any module that is imported at runtime but
   not copied.

Refinements to consider:
- Only flag modules that are actually imported by `app.py`/`main.py` (directly
  or transitively), to avoid false positives on dev-only or test-only modules.
  A simpler v1 can just require *all* tracked root modules be copied and
  explicitly allowlist any intentional exceptions.
- Mirror the same idea for top-level package directories (e.g. `validation/`,
  `baml_client/`) so a missing `COPY dir/ dir/` is also caught.

## Where it runs

- **CI**: add as a step in the GitHub Actions workflow (fast, no Docker build
  required — it's pure static analysis).
- **Optionally** wire into the repo pre-commit hook so it's caught even
  earlier, before a commit lands.


## Acceptance criteria


- Adding a tracked root module imported by `app.py`/`main.py` without a
  corresponding `COPY` line fails CI with a clear message naming the module.
- Existing repo state passes the check (after the image_conversion hotfix).
- The check needs no Docker build to run (static parse only), so it's fast.
- Documented briefly (README or CLAUDE.md) so future contributors know why it
  exists.

## Notes

- Out of scope: validating `requirements.txt` completeness or non-Python
  assets. This is specifically about local module COPY coverage in the
  Dockerfile.

<!-- DONE -->
