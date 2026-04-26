---
github_issue: 60
---
# Handoff: Migration from Streamlit Community Cloud to Render

**Date:** 2026-04-25
**GitHub Issue:** #60
**Status:** Research complete, implementation not started

---

## Background

Receipt Ranger is currently deployed on Streamlit Community Cloud (SCC). SCC has several issues that make the app look unprofessional:

- Cold starts / "wake up" screen when the app hasn't been visited recently
- "Fork" button and GitHub icon in the top-right corner linking to source code
- User profile avatar in the bottom-right corner
- "Made with Streamlit" branding

The goal is to move to a professional deployment that eliminates all of these while keeping Streamlit as the framework.

---

## Research Summary

Seven platforms were evaluated. The hard constraint is **WebSocket support** — Streamlit requires persistent WebSocket connections via `/_stcore/stream`. Without this, the app does not function (this is why AWS App Runner failed previously).

### Platforms Evaluated

| Platform | WebSocket | Always-On Cost | Complexity | Verdict |
|---|---|---|---|---|
| **Render** | YES | $7/mo (Starter) | LOW | **RECOMMENDED** |
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

## Migration Plan

### Prerequisites
- Render account created
- Payment method added (Starter plan, $7/month)

### Step 1: Create Render Web Service
- Connect GitHub repo (`gness1804/receipt-ranger`)
- Select "Docker" as the build environment (Render will use the existing `Dockerfile`)
- Set instance type to Starter ($7/mo, always-on)

### Step 2: Configure Environment Variables
Set these in Render's service environment variables:

| Variable | Value | Notes |
|---|---|---|
| `SESSION_SECRET` | (from current SCC secrets) | Mark as secret |
| `OWNER_OPENAI_API_KEY` | (from current SCC secrets) | Mark as secret |
| `OWNER_ANTHROPIC_API_KEY` | (from current SCC secrets) | Mark as secret |
| `ENABLE_GOOGLE_SHEETS` | `true` | |
| `GOOGLE_SHEETS_CREDENTIALS` | (base64-encoded service_account.json) | Mark as secret |

### Step 3: Verify Deployment
- Confirm the app loads on the Render-provided `*.onrender.com` URL
- Test WebSocket connectivity (app should be fully interactive, no "connecting..." issues)
- Test receipt upload + processing end-to-end
- Test Google Sheets integration
- Verify no Render branding appears on the page

### Step 4: Update DNS (Cloudflare)
- Add custom domain in Render dashboard
- In Cloudflare, update the CNAME for `receipt-ranger.com` to point to the Render service URL
- **Set Cloudflare proxy to DNS-only (grey cloud)** — Render handles its own SSL; orange cloud will conflict
- Verify SSL works on `receipt-ranger.com`

### Step 5: Hide Remaining Streamlit Branding
The Streamlit hamburger menu and "Made with Streamlit" footer still appear in any Streamlit deployment. To remove them:

1. In `.streamlit/config.toml`, add:
   ```toml
   [ui]
   hideTopBar = true
   ```

2. In `app.py`, add CSS to hide the footer:
   ```python
   st.markdown("""<style>footer {visibility: hidden;}</style>""", unsafe_allow_html=True)
   ```

### Step 6: Decommission SCC
- Remove the app from Streamlit Community Cloud dashboard
- Remove any SCC-specific configuration that is no longer needed

### Step 7: Update Documentation
- Update `README.md` with new deployment info
- Update the CLAUDE.md project instructions (deployment section references SCC)
- Update agent memory with new deployment status

---

## Known Considerations

- **BAML version pinning:** `baml-py==0.218.0` must remain exact in `requirements.txt`. Render builds from the Dockerfile, which uses `requirements.txt`, so this works as-is.
- **Cloudflare DNS-only:** Same lesson from SCC — Render handles SSL, so Cloudflare must be grey cloud (DNS-only) to avoid certificate conflicts.
- **Ephemeral filesystem:** Render's filesystem resets on each deploy/restart. Receipt images are processed in-memory and not stored locally, so this is not an issue.
- **Port:** The Dockerfile exposes 8501. Render auto-detects this from the `EXPOSE` directive.
