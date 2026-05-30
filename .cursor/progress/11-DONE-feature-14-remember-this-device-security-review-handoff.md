---
github_issue: 82
---
# Feature 14 Remember This Device Security Review Handoff

## Working directory

`~/Desktop/receipt-ranger`

## Contents

## Working directory

`~/Desktop/receipt-ranger`

## Current branch

`feature/14-remember-this-device` — **nothing is committed yet.** The working
tree has uncommitted changes (see "Working tree state" below).

## Session summary (2026-05-29)

This session covered three things: (1) deciding NOT to build a PWA, (2) building
the chosen alternative (feature #14, "remember this device"), and (3) a full
security review.

### 1. PWA decision — DECLINED (issue #76 / CFS feature 12 closed)

Evaluated building Receipt Ranger as a Progressive Web App. Decided against it
and closed issue #76 (CFS feature 12 → `12-DONE-…`). Reasoning recorded on the
GitHub issue:
- A PWA doesn't fix the real friction (the API-key re-entry); installability is
  just polish.
- Streamlit has no native PWA support; making it installable needs a
  reverse-proxy/head-injection layer + WebSocket proxying — the same class of
  problem that broke the old App Runner migration. High deploy risk, low payoff.
- Offline value is limited (extraction needs network + key + LLM).

### 2. Feature #14 — BUILT (issue #81 / CFS feature 14) — code complete, untested in-app

Added an opt-in "Keep my key on this device" selector to the web app's API-key
entry, replacing the fixed 7-day cookie with three choices:
- **This session only** — session cookie, cleared on browser close (shared machines)
- **7 days** — DEFAULT (index 1), preserves prior behavior, no regression
- **Remember this device (90 days)** — opt-in convenience (e.g. a spouse's phone)

Decisions confirmed by the user: 90-day "remember" TTL; 7-day default; include a
session-only option.

Implementation (all in `app.py`):
- New constants: `SESSION_ONLY_MAX_AGE` (None), `DEFAULT_KEY_MAX_AGE` (7d),
  `REMEMBER_DEVICE_MAX_AGE` (90d), `KEY_PERSISTENCE_LABELS`,
  `KEY_PERSISTENCE_MAX_AGES`, `DEFAULT_KEY_PERSISTENCE_INDEX = 1`.
- New helper `set_session_cookie()` — omits `max_age` for session-only, keeps
  `secure=True` on every path.
- The chosen TTL threads through the existing DEFERRED cookie-save pattern in
  `main_app()` (cookie.set must run on the render AFTER `st.rerun()`, never
  inline) to both `rr_session` and `rr_provider`.
- `init_session_state()` seeds `api_key_save_pending_max_age`.
- Updated the expander copy + added a help tooltip.

Tests: 9 new tests in `tests/test_app.py`. **Full suite: 176 passed.** ruff +
black clean. Passed an Opus QA review (ian-backend-leader): clean, "ship it."

NOT yet done for #14: manual in-app verification (launch Streamlit, enter a key
under each option, confirm cookie lifetime in DevTools); commit; version bump
(would be a MINOR bump per house rules, AFTER the work commit).

### 3. Security review (/security-check) — findings

App code is well-secured (encrypted keys, no committed secrets, no XSS/injection
surface, feature #14 clean). Findings:

- **CRITICAL — `deploy.sh` leaks all production secrets to stdout.**
  `run_cmd()` (`deploy.sh:70-77`) echoes the full command (`>>> $*` on real runs,
  `[DRY RUN] $*` on dry runs); that command interpolates plaintext
  `SESSION_SECRET` (the Fernet key protecting every user's key), `OWNER_*_API_KEY`,
  and base64 service-account JSON (`deploy.sh:167-171, 205-209`). The
  `aws apprunner` responses are also unredirected. NOTE: this is DEAD AWS App
  Runner tooling — the app runs on Render now — and is UNRELATED to feature #14.
- **CRITICAL (doc) — false control claim.** `~/CLAUDE.md` ("Secrets in script
  output") claims this `deploy.sh` already has `redact()` + `run_cmd_secret()`.
  Those functions DO NOT EXIST. The policy documents a non-existent safety net.
- **MEDIUM — no cryptographic TTL on token decrypt.** `decrypt_api_key`
  (`session.py:46-56`) calls Fernet `decrypt()` without `ttl=`, so a captured
  token never expires server-side. The new 90-day cookie widens the replay
  window. FIX: pass `ttl=REMEMBER_DEVICE_MAX_AGE` to `_fernet.decrypt(...)`.
  This is the one security item directly tied to feature #14 — recommend folding
  it into this branch before merge.
- **LOW** — `SESSION_SECRET` soft-fails to a random key when unset
  (`session.py:17-28`); consider failing hard in prod.
- **LOW** — cookies lack HttpOnly/SameSite (inherent to
  streamlit-cookies-controller's JS cookies; mitigated by the encrypted token).

Verified directly against files: the deploy.sh leak, no tracked secrets
(`git ls-files` clean; `.gitignore`/`.dockerignore` cover `.env` +
`service_account.json`), and no stored XSS (receipt data rendered via
auto-escaping `st.table`/`st.write`, not `unsafe_allow_html`).

## Working tree state (uncommitted)

- `M app.py`, `M tests/test_app.py` — feature #14
- CFS doc rename: `12-…` → `12-DONE-…` (PWA closure)
- New: `14-optional-remember-this-device-…md` (CFS feature 14)
- Branch `feature/14-remember-this-device` carries all of the above.

## Recommended next steps (priority order)

1. **Fold the MEDIUM fix into feature #14:** add `ttl=` to `decrypt_api_key`
   (+ a test), so server-side token expiry matches the 90-day cookie.
2. **Manually verify feature #14 in the running app** (cookie lifetimes in
   DevTools for each option), then commit the branch and offer a MINOR version
   bump.
3. **Handle the CRITICAL deploy.sh leak** (separate change): preferably DELETE
   `deploy.sh` + the AWS `deploy/` artifacts (unused on Render), or add real
   redaction. Then CORRECT the false `~/CLAUDE.md` claim (ask before editing the
   global CLAUDE.md). Consider opening a CFS bug to track it.
4. Optional hardening: fail-hard `SESSION_SECRET`; add `pip-audit` to CI.

## Pointers

- GitHub issue #81 (CFS feature 14, OPEN) — the active feature.
- GitHub issue #76 (CFS feature 12, CLOSED) — PWA, declined.
- Unrelated: handoff doc #9 / GitHub issue #63 ("Duplicate Thumbnails") is still
  OPEN and incomplete — left untouched pending user decision on whether to close.

## Acceptance criteria

<!-- DONE -->
