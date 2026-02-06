---
github_issue: 20
---
# Deployment Completion and Google Sheets Feature Flag

## Working directory

`~/Desktop/receipt-ranger`

## Contents

**Date:** 2026-02-06
**Branch:** `main` (merged from `feature/aws-deployment` and `hotfix/google-sheets-feature-flag`)
**Version:** v0.6.0
**Status:** Deployment working; Google Sheets disabled on production via feature flag

---

## Summary

This session resolved the blocking WebSocket issue from the previous session (progress/5) and got the Streamlit app fully working at `https://receipt-ranger.com`. Also added a feature flag to disable Google Sheets on the public deployment.

---

## Issues Resolved

| Issue | Root Cause | Solution |
|-------|-----------|----------|
| WebSocket failure through Cloudflare | Cloudflare "Flexible" SSL downgrades `wss://` to `ws://` | Switched to "Full" SSL with self-signed cert on EC2 |
| 403 on WebSocket stream endpoint | Streamlit CORS check rejects proxied requests | Set `enableCORS = false` in `.streamlit/config.toml` |
| 403 persisting after CORS fix | Streamlit XSRF check also rejects proxied requests | Set `enableXsrfProtection = false` in `.streamlit/config.toml` |
| Cloudflare blocking repeated requests | WAF rate limiting rule (100 req/10s) too aggressive for Streamlit | Disabled/adjusted the rate limiting rule in Cloudflare |
| Port 8501 unavailable (6000+ restarts) | Zombie Streamlit processes from crash loop | `sudo lsof -ti :8501 \| xargs -r sudo kill -9` then restart |
| Public users could write to owner's Google Sheet | Hardcoded service account + spreadsheet name | Added `ENABLE_GOOGLE_SHEETS` env var (false on EC2) |

## Key Lesson Learned

Streamlit behind a reverse proxy (Cloudflare + Nginx) requires **three** things:
1. `enableXsrfProtection = false`
2. `enableCORS = false`
3. Cloudflare SSL mode set to **Full** (not Flexible)

This is now documented in `deploy/README.md` under Troubleshooting.

---

## Changes Made

### Commits merged to main

1. **SSL Nginx config** — Added port 443 server block with self-signed cert, port 80 redirect
2. **Deployment docs** — SSL setup instructions, "Run on" labels on all code blocks, WebSocket troubleshooting section
3. **PEM key path** — Updated from `~/Downloads` to `~/Secrets`
4. **Nginx config copy commands** — Added `git pull` + `sudo cp` to step 3.3
5. **Streamlit config** — `enableXsrfProtection = false`, `enableCORS = false`
6. **CFS closures** — features/5, progress/5
7. **Google Sheets feature flag** — `ENABLE_GOOGLE_SHEETS` env var, dynamic app description
8. **Version bump** — v0.5.0 -> v0.6.0

### New files created

- `~/scripts/aws-sg-add-cloudflare-ips` — Script to bulk-add Cloudflare IP CIDR blocks to an AWS security group for port 443
- `.cursor/features/7-per-user-google-sheets-integration.md` — CFS feature for future Google Sheets work (GitHub #19)

---

## Pending EC2 Deployment

The feature flag commit has NOT been deployed to EC2 yet. Run:

```bash
cd ~/receipt-ranger && git pull
sudo cp deploy/receipt-ranger.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart receipt-ranger
```

This will pick up the `ENABLE_GOOGLE_SHEETS=false` env var in the systemd service file, hiding Google Sheets from the public app.

---

## Cloudflare Configuration (Current State)

- **SSL/TLS mode:** Full
- **DNS A record:** Proxied (orange cloud)
- **Rate limiting rule:** Disabled (needs to be re-enabled with Streamlit-friendly settings)
- **Always Use HTTPS:** On
- **Port 80 inbound rule:** Removed from AWS security group

---

## Open Items

1. **Re-enable Cloudflare rate limiting** — The rule was disabled to fix WebSocket issues. It should be re-enabled with exclusions for Streamlit endpoints (`/_stcore/stream`, `/_stcore/health`, `/_stcore/host-config`), or with a higher threshold.
2. **Per-user Google Sheets integration** — CFS features/7 (GitHub #19). User's preferred approach: let each user upload their own Google service account JSON and specify their own spreadsheet.
3. **Todoist `cfs` label** — The label doesn't appear in the Todoist API's label list, even though tasks with it exist. May need to be recreated.
