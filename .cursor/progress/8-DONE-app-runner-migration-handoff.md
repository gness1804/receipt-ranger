---
github_issue: 46
---
# Handoff: App Runner Migration — Pivot to Streamlit Community Cloud

**Date:** 2026-02-21
**GitHub Issue:** #45 (closed)
**CFS Issue:** refactors/2 (closed — route changed)

---

## What We Did

Attempted to migrate Receipt Ranger from EC2 to AWS App Runner. Created the
following files (all still on the `refactor/ec2-to-app-runner` branch):

- **`Dockerfile`** — Python 3.11-slim, Streamlit on port 8501, `--platform linux/amd64` for M4 compatibility
- **`.dockerignore`** — excludes secrets, state files, BAML source, tests, output
- **`deploy.sh`** — `--dry-run`/`--build-only` flags, ECR repo creation, IAM role, App Runner create/update with timestamp-based image tags to prevent caching
- **`sheets.py`** (modified) — `get_gspread_client()` now checks a `GOOGLE_SHEETS_CREDENTIALS` env var (base64-encoded JSON) before falling back to the `service_account.json` file — necessary for any containerized deployment

---

## Issues Fixed Along the Way

| Error | Cause | Fix |
|-------|-------|-----|
| `ModuleNotFoundError: No module named 'dotenv'` | `requirements.txt` missing `python-dotenv`, `cryptography`, `streamlit-cookies-controller` | Added all three to `requirements.txt` |
| `ImportError: baml-py out of date` | `requirements.txt` used `baml-py>=0.218.0`; pip installed 0.219.0 which doesn't match the generated `baml_client/` | Pinned to `baml-py==0.218.0` |
| App Runner not redeploying | `IMAGE_TAG` defaulted to `latest`; App Runner ignores `update-service` calls with the same tag | Changed default to `$(date +%Y%m%d%H%M%S)` |
| Platform warning on local Docker run | Image built for `linux/amd64`, M4 is ARM64 | Expected/harmless — QEMU emulation for local testing |

---

## Why App Runner Didn't Work

After fixing all app-level errors, the Docker image ran correctly on localhost but
failed on App Runner with perpetual flashing and WebSocket errors.

**Evidence from browser DevTools:**
- HTTP requests (`/_stcore/health`, `/_stcore/host-config`) succeeded on App Runner
- WebSocket connections (`/_stcore/stream`) received **no response** at all —
  "Provisional headers are shown" with an empty Response headers section
- Streamlit retried the WebSocket connection in a loop, causing the flashing

**Root cause:** App Runner's internal proxy does not properly forward WebSocket
upgrade requests (HTTP/1.1 `Upgrade: websocket`) to the container. HTTP works
fine; persistent WebSocket connections do not pass through.

Friendly Advice Columnist works on App Runner because it's a REST API with no
WebSocket connections. Streamlit requires WebSocket for all real-time
communication and cannot function without it.

---

## Current State

- The EC2 instance is still running and serving the app — **do not terminate yet**
- All files created this session are on the `refactor/ec2-to-app-runner` branch
- The Docker image is functional and correct — useful if a future target supports
  WebSocket (e.g., ECS Fargate)

---

## Recommended Path: Streamlit Community Cloud

Free, zero-infrastructure, designed for Streamlit, WebSocket handled natively,
custom domain support.

### Step 1 — Deploy the App

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
2. Click **New app**
3. Select repo `receipt-ranger`, branch `main`, entry point `app.py`
4. Under **Advanced settings**, add secrets:

```toml
SESSION_SECRET = "..."                  # Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
OWNER_OPENAI_API_KEY = "sk-..."
OWNER_ANTHROPIC_API_KEY = "sk-ant-..."  # Optional
ENABLE_GOOGLE_SHEETS = "true"
GOOGLE_SHEETS_CREDENTIALS = "..."       # Base64-encoded service_account.json:
                                        # base64 -i service_account.json | tr -d '\n'
```

5. Click **Deploy** — app will be live at `https://[app-name].streamlit.app`

### Step 2 — Custom Domain via Cloudflare

1. In Streamlit Community Cloud: app → **Settings → Custom domain** → enter your domain
2. Copy the CNAME target Streamlit provides
3. In Cloudflare DNS:
   - Delete the A record pointing to the EC2 Elastic IP
   - Add a CNAME: `your-domain.com` → Streamlit's CNAME target
   - Set to **DNS only (grey cloud)** — Streamlit handles SSL; Cloudflare proxy can conflict
4. Streamlit provisions an SSL certificate automatically

### Step 3 — Cleanup After Cutover

- [ ] Confirm app and custom domain working on Streamlit Community Cloud
- [ ] Terminate EC2 instance
- [ ] Release the Elastic IP (charged when unattached)
- [ ] Delete App Runner service (optional)
- [ ] Delete ECR repository (optional, small storage cost)
- [ ] Merge or delete the `refactor/ec2-to-app-runner` branch

<!-- DONE -->
