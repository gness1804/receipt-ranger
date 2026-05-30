---
github_issue: 81
---
# Optional Remember This Device For Longer Lived Api Key Persistence

## Working directory

`~/Desktop/receipt-ranger`

## Contents

## Working directory

`~/Desktop/receipt-ranger`

## Overview

Add an opt-in "Remember this device" option to the web app's API-key entry so a
trusted user (e.g. a household member) can paste their key once and not be
prompted again for an extended period. Today the encrypted-key cookie has a
fixed 7-day TTL, so the key must be re-entered weekly and on every new install.

This is the chosen alternative to building a PWA (see closed issue #76 / CFS
feature 12). It solves the actual friction — repeated key entry — without
changing the app's infrastructure or security model: it remains a public,
bring-your-own-key app with no user accounts and no shared owner key.

## Motivation

- Lower the barrier for a second household user who is uncomfortable re-pasting
  an API key every 7 days. The owner can set up the key once on her device with
  "Remember this device" checked, after which she rarely (if ever) sees the
  key prompt.
- Keep the security posture intact: no auth gate, no server-side owner-key
  lane, no new credential to protect, no shared-spend/abuse vector. The only
  marginal change is a longer-lived encrypted cookie on a trusted device, fully
  opt-in.

## Current behavior (as of this writing)

- `app.py` persists the Fernet-encrypted key token in a browser cookie
  (`rr_session`) plus the provider (`rr_provider`) via `streamlit-cookies-controller`.
- The cookie TTL is hardcoded: `max_age=7 * 24 * 60 * 60` at two `cookie.set`
  call sites (around `app.py:892` and `app.py:897`).
- The API-key expander copy states the key is "stored as a secure browser
  cookie for 7 days" (around `app.py:418`).
- The key is always Fernet-encrypted before being written to the cookie
  (`session.encrypt_api_key`), and `secure=True` keeps it HTTPS-only.

## Proposed approach

1. Add an opt-in checkbox in the API-key expander, e.g. "Remember this device
   for 90 days" (default UNCHECKED to preserve current behavior).
2. When unchecked: keep today's 7-day TTL (no regression).
   When checked: use the longer TTL (proposed default 90 days — see Decisions).
3. Thread the chosen TTL through the deferred-save flow:
   - Store the desired `max_age` alongside the existing
     `api_key_save_pending_token` / `api_key_save_pending_provider` deferred-save
     state, so the value is available when `cookie.set(...)` actually runs on the
     next render (the existing deferred-save pattern must be preserved — calling
     `cookie.set` immediately before `st.rerun()` drops the write).
   - Apply the same `max_age` to both the `rr_session` and `rr_provider`
     `cookie.set` calls.
4. Replace the hardcoded "7 days" copy (`app.py:418`) with text that reflects
   the actual duration, and clarify that "Remember this device" should only be
   used on a personal/trusted device.
5. Define the TTL as a named constant (e.g. `REMEMBER_DEVICE_MAX_AGE` and
   `DEFAULT_SESSION_MAX_AGE`) rather than inline arithmetic, for clarity and
   easy future tuning.

## Security considerations

- No change to the threat model beyond a longer-lived cookie: the stored value
  is still a Fernet-encrypted token, never plaintext, and `secure=True` /
  HTTPS-only is retained.
- "Remember this device" is explicitly opt-in and worded as device-trust, so a
  longer-lived cookie is never a surprise on a shared/public machine.
- Confirm the encrypted token is the only sensitive value persisted; the cookie
  must never store the plaintext key or anything that isn't Fernet output.
- A longer TTL widens the window in which a stolen/exfiltrated cookie could be
  replayed. Acceptable for a trusted personal device and consistent with the
  user's own-key funding model, but should be called out in the security
  review for this branch.

## Acceptance criteria

- An opt-in "Remember this device" control exists in the API-key entry UI,
  defaulting to off.
- With the option off, the cookie TTL remains 7 days (no behavior change).
- With the option on, the encrypted-key cookie persists for the longer TTL and
  the key is not re-prompted until that window elapses or the user clears it.
- The "Change API key" / clear flow still removes the cookie regardless of the
  chosen TTL.
- UI copy accurately reflects the active duration and the device-trust caveat.
- The key is still Fernet-encrypted at rest in the cookie; no plaintext is
  persisted.
- Tests cover the TTL-selection logic (and the deferred-save path if feasible
  to unit-test).

## Decisions to confirm before implementation

- Default "remember" TTL: 90 days proposed. Alternatives: 30 days, 180 days,
  1 year. (Longer = more convenient but a larger replay window.)
- Checkbox default: off (recommended, no regression) vs. on.
- Whether to also offer a "session only" (no persistence) choice for shared
  machines, or keep the current 7-day as the un-checked default.

## Out of scope

- Any auth gate, login, or server-side owner-key lane.
- PWA / installability work (declined in issue #76).
- Changes to the CLI or the core extraction pipeline.

## Acceptance criteria

<!-- DONE -->
