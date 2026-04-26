---
github_issue: 60
---
# Handoff: Migration from Streamlit Community Cloud to Render

**Date:** 2026-04-25 (research) / 2026-04-26 (migration)
**GitHub Issue:** #60
**Status:** Migration complete; remaining cleanup items listed at bottom

---

## Background

Receipt Ranger was previously deployed on Streamlit Community Cloud (SCC). SCC had several issues that made the app look unprofessional:

- Cold starts / "wake up" screen when the app hadn't been visited recently
- "Fork" button and GitHub icon in the top-right corner linking to source code
- User profile avatar in the bottom-right corner
- "Made with Streamlit" branding

The goal was to move to a professional deployment that eliminates all of these while keeping Streamlit as the framework.

---

## Research Summary

Seven platforms were evaluated. The hard constraint is **WebSocket support** — Streamlit requires persistent WebSocket connections via `/_stcore/stream`. Without this, the app does not function (this is why AWS App Runner failed previously).

### Platforms Evaluated

| Platform | WebSocket | Always-On Cost | Complexity | Verdict |
|---|---|---|---|---|
| **Render** | YES | $7/mo (Starter) | LOW | **CHOSEN** |
| **Railway** | YES | $5-10/mo | VERY LOW | Strong alternative |
| **AWS EC2** | YES (nginx) | $10-14/mo | MEDIUM | Viable but high ops burden |
| **AWS ECS Fargate** | YES (ALB) | $20-22/mo | HIGH | ALB cost alone exceeds Render |
| **Google Cloud Run** | YES* | $0-50/mo | LOW-MEDIUM | 60-min WebSocket timeout; always-on = ~$50/mo |
| **Azure Container Apps** | YES | $0-50/mo | MEDIUM-HIGH | No advantage over Cloud Run |
| **DigitalOcean App Platform** | YES | $5-12/mo | LOW | 512MB RAM may be tight on $5 plan |

### Why Render Won

1. **Full WebSocket support**, explicitly documented — no edge cases
2. **$7/month Starter plan is always-on** — no cold starts, no wake-up screen
3. **Deploys directly from existing Dockerfile** — minimal migration effort
4. **Zero infrastructure to manage** — no VPC, ALB, IAM, nginx, or cert renewals
5. **Custom domain + SSL** — works with Cloudflare (DNS-only / grey cloud for CNAME)
6. **No third-party branding** — no Render icons, no GitHub links, no avatars injected into the page
7. **Ephemeral filesystem is not a problem** — receipts are processed in-memory, not stored between sessions

### Why Not the Others

- **Railway:** Very close second. Slightly cheaper but WebSocket support is less explicitly documented, and HTTP/2 edge cases have been reported.
- **EC2:** Works but you own all ops permanently (patching, nginx, Docker, Certbot). Already tried and terminated once.
- **Fargate:** ALB minimum fee (~$16-18/mo) alone exceeds total Render cost. Massive infrastructure complexity.
- **Cloud Run:** 60-minute WebSocket timeout disconnects users who leave tabs open. Always-on pricing (~$50/mo) is prohibitive.

---

## What Was Done (2026-04-26)

### Phase 1: Branding Cleanup (commit `d52dcf1`)
- Set `hideTopBar = true` in `.streamlit/config.toml`
- Injected CSS in `app.py` to hide `#MainMenu` and `footer`
- Verified locally with `streamlit run app.py` — no Streamlit branding visible on page

### Phase 2: Render Setup
- Created Render account
- Created Web Service connected to the `gness1804/receipt-ranger` repo
- Set tracked branch to `deploy/upgrade-to-more-professional-hosting` (will switch to `main` after merge — see Remaining To-Dos)
- Selected Docker runtime (Render auto-detected the existing `Dockerfile`)
- Selected Starter plan ($7/mo, always-on)
- Added all required environment variables in Render's dashboard:
  - `SESSION_SECRET` — **rotated** (new Fernet key, not the SCC value)
  - `OWNER_OPENAI_API_KEY`
  - `OWNER_ANTHROPIC_API_KEY`
  - `ENABLE_GOOGLE_SHEETS=true`
  - `GOOGLE_SHEETS_CREDENTIALS` (base64-encoded service account JSON, same as SCC)

### Phase 3: First Deploy + Bug Fix (commit `74ac66a`)
- First Render build failed with `ModuleNotFoundError: No module named 'validation'`
- Cause: Dockerfile only copied `app.py`, `main.py`, `session.py`, `sheets.py`, `pyproject.toml`, and `baml_client/` — but `validation/` (used by `main.py` for prompt injection detection) was missing
- Fix: Added `COPY validation/ validation/` to the Dockerfile
- Deploy succeeded after pushing the fix

### Phase 4: Functional Verification
On `https://receipt-ranger-xcjm.onrender.com/`:
- Visual / branding check: passed (no Fork button, GitHub icon, avatar, footer, or hamburger menu)
- WebSocket connectivity: passed (UI fully interactive, no "connecting..." spinner)
- Receipt upload + processing: passed
- Google Sheets integration: passed (owner detection working)
- Idle reliability spot-check: passed (no wake-up state after 5 min idle)

### Phase 5: DNS Cutover
- Added `receipt-ranger.com` and `www.receipt-ranger.com` to Render's custom domains
- In Cloudflare:
  - Edited the existing A record for the apex (was `192.0.2.1`, the placeholder for the SCC redirect): changed to **CNAME** pointing to `receipt-ranger-xcjm.onrender.com`, set to **DNS only** (grey cloud)
  - Edited the existing CNAME for `www`: changed target to `receipt-ranger-xcjm.onrender.com`, set to **DNS only** (grey cloud)
  - Cloudflare's CNAME flattening at apex worked fine — no need to use Render's `216.24.57.1` A-record fallback
- Render verified DNS and issued Let's Encrypt SSL certs
- Verified `https://receipt-ranger.com` and `https://www.receipt-ranger.com` both serve the app from Render (confirmed via `curl -I` showing `x-render-origin-server: TornadoServer/6.5.5`)

### Phase 6: Cleanup of Old SCC Redirect
- Deleted the "Route to Streamlit site" redirect rule in Cloudflare → Rules → Redirect Rules
- Browser cache of the old 301 redirect was a temporary issue — fixed by testing in incognito or hard-refresh

### Phase 7: Documentation Updates (commit `0ead38d`)
- Updated `README.md` Deployment section to describe Render setup
- Updated `CLAUDE.md` to add Deployment section with Render details and BAML pinning constraint; dropped stale "MVP, backend only" framing
- Updated agent memory (`MEMORY.md`) to reflect Render as current deployment with key lessons learned

---

## Key Lessons Learned

- **Dockerfile must `COPY` ALL local Python modules used at runtime.** Easy to miss — the `validation/` directory was an oversight that wasn't caught until Render's first build.
- **301 redirects get cached aggressively by browsers.** After DNS cutover, the user's normal browser still sent them to Streamlit because the old 301 was cached. Incognito works immediately; normal browsers may need cache clearing or hard refresh.
- **Cloudflare CNAME flattening at apex works fine with Render** — no need to use the A-record + IP fallback that Render suggests.
- **Render does NOT auto-switch tracked branches** — when merging the deploy branch into `main`, you must manually update the tracked branch in Render's Settings → Build & Deploy.
- **CFS pre-commit sync may report `content_conflict`** for handoff docs paired with GitHub issues. Doesn't block commits; resolve in interactive shell with `cfs gh sync` if needed.

---

## Remaining To-Dos

These are not blocking and can be done at the user's pace.

### High Priority

1. **Push the doc commits** — `git push` to get the README/CLAUDE.md updates onto the remote.
2. **Open a PR** from `deploy/upgrade-to-more-professional-hosting` → `main` and merge.
3. **Update Render's tracked branch** — in Render → Settings → Build & Deploy, change the branch from `deploy/upgrade-to-more-professional-hosting` to `main`. This is **manual** — Render does not auto-switch when you merge. Do this **before** deleting the feature branch.
4. **Decommission SCC** — once Render has been stable for a day or two, remove the app from the Streamlit Community Cloud dashboard. Also remove any SCC-specific config that is no longer needed (e.g., references to Streamlit secrets in any docs that aren't already updated).
5. **Bump version** — per house rules, this migration is a significant refactor; run `bump2version minor` on a fresh commit after merging.

### Low Priority / Polish

6. **Replace Streamlit's default favicon.** The deployed app still serves Streamlit's default flame favicon at `./favicon.png` (a static asset baked into the Streamlit Python package). The `page_icon="🧾"` in `st.set_page_config()` only swaps it dynamically via JS, so the browser briefly shows the flame and may cache it. Fix: add a custom 32x32 PNG to the repo (e.g., `assets/favicon.png`) and overwrite Streamlit's default in the Dockerfile:
   ```dockerfile
   COPY assets/favicon.png /usr/local/lib/python3.11/site-packages/streamlit/static/favicon.png
   ```
   Skipped during the migration to avoid scope creep and unintended side effects.

7. **Optional: clean up `deploy/` directory.** It contains historical EC2 + nginx artifacts (`nginx.conf`, `receipt-ranger.service`, `README.md`, a Medium PDF) that are now obsolete. Either delete or move to an `archive/` folder. README.md already labels these as historical.

---

## Known Considerations (carryover from research)

- **BAML version pinning:** `baml-py==0.218.0` must remain exact in `requirements.txt`. BAML enforces an exact match between the runtime and the generator that produced `baml_client/`. A `>=` pin will silently break in fresh Docker builds.
- **Cloudflare DNS-only:** Render handles its own SSL via Let's Encrypt — Cloudflare proxy (orange cloud) will break SSL/WebSockets.
- **Ephemeral filesystem:** Render's filesystem resets on each deploy/restart. Receipt images are processed in-memory, so this is not an issue for this app.
- **Port:** The Dockerfile exposes 8501. Render auto-detects this from the `EXPOSE` directive.

<!-- DONE -->
