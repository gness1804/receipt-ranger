---
github_issue: 16
---
# AWS Deployment Handoff - WebSocket Troubleshooting

## Working directory

`~/Desktop/receipt-ranger`

## Contents

**Date:** 2026-02-05
**Branch:** `feature/aws-deployment`
**CFS Issue:** features/5 (GitHub #11)
**Status:** Phases 1-4 mostly complete; stuck on WebSocket issue through Cloudflare

---

## Summary

This session continued the AWS deployment. Phases 1-3 were already complete. We worked through Phase 4 (Deploy Application) and resolved multiple issues, but hit a blocking WebSocket problem when accessing the app through Cloudflare.

**Key finding:** The app works perfectly when accessed via direct IP (`http://3.22.127.222`), but WebSocket connections fail when accessed through the domain (`http://receipt-ranger.com` or `https://receipt-ranger.com`).

---

## What Was Completed This Session

### Issues Resolved

| Issue | Root Cause | Solution |
|-------|-----------|----------|
| Can't SSH into EC2 | VPN changed IP address | Disconnect VPN, or add VPN IP to security group |
| 521 Web Server Down | Cloudflare SSL mode was "Full" | Changed to "Flexible" |
| 521 persisting | Security group missing HTTP port 80 | Added Cloudflare IP ranges to allow port 80 |
| Service failing to start | Missing `output/` and `logs/` directories | Created directories with `mkdir -p` |
| ModuleNotFoundError: pydantic | Dependency not installed via requirements.txt | Installed manually with `pip install pydantic` |
| feature branch not on EC2 | Branch wasn't pushed to GitHub | Pushed branch, then fetched on EC2 |

### Configuration Changes Made on EC2

1. Updated `/etc/nginx/nginx.conf`:
   - Changed `server_name YOUR-DOMAIN.COM` to `server_name receipt-ranger.com`

2. Created required directories:
   ```bash
   mkdir -p ~/receipt-ranger/output
   mkdir -p ~/receipt-ranger/logs
   ```

3. Installed missing dependency:
   ```bash
   pip install pydantic
   ```

### Cloudflare Configuration

- SSL/TLS mode: **Flexible** (required - "Full" causes 521 errors)
- Added Cloudflare IP ranges to AWS security group for port 80

---

## Current Blocking Issue

### WebSocket Failure Through Cloudflare

**Symptoms:**
- App loads but shows infinite loading spinner
- Browser console shows repeated WebSocket errors: `wss://receipt-ranger.com/_stcore/stream failed`
- Works perfectly via direct IP: `http://3.22.127.222`

**What We Tried:**
- Verified Nginx WebSocket config (has correct `Upgrade` and `Connection` headers)
- Disabled XSRF protection in Streamlit (didn't help)
- Grey cloud (DNS only) in Cloudflare (didn't help - local DNS still cached Cloudflare IPs)
- Flushed local DNS cache (command failed on Mac)

**Root Cause Hypothesis:**
Cloudflare's Flexible SSL mode may not properly handle WebSocket upgrades. The connection path is:
```
Browser (wss://) → Cloudflare → EC2 (ws://)
```

The protocol downgrade from WSS to WS may be causing issues.

---

## Proposed Solution (Not Yet Implemented)

Set up HTTPS on the origin server so Cloudflare can use "Full" SSL mode:

1. Generate a self-signed SSL certificate on EC2
2. Configure Nginx to listen on port 443 with SSL
3. Update AWS security group to allow port 443 from Cloudflare IPs
4. Change Cloudflare SSL mode from "Flexible" to "Full"

This keeps the entire path encrypted and avoids protocol mismatches.

**Commands to implement:**
```bash
# Generate self-signed cert
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/private/nginx-selfsigned.key \
  -out /etc/ssl/certs/nginx-selfsigned.crt

# Update Nginx config to use SSL (need to modify nginx.conf)
# Then change Cloudflare SSL mode to Full
```

---

## Temporary Changes to Revert

Before next session, these temporary debugging changes should be reverted:

### On EC2 Instance

1. **XSRF Protection** - Change back to `true`:
   ```bash
   vim ~/receipt-ranger/.streamlit/config.toml
   # Change: enableXsrfProtection = false
   # To:     enableXsrfProtection = true
   ```

### In Cloudflare Dashboard

1. **Proxy mode** - Turn orange cloud back ON (if still grey)
   - DNS → A record → Click to make orange

2. **Always Use HTTPS** - Turn back ON (if it was disabled)
   - SSL/TLS → Edge Certificates → Always Use HTTPS → ON

---

## Files That Need Updating (Local Repo)

Once deployment is working, these local files should be updated:

1. **`requirements.txt`** - Add `pydantic` explicitly (it wasn't being installed as a transitive dependency)

2. **`deploy/README.md`** - Clarify that Cloudflare SSL must be "Flexible" (not "Full") OR set up origin SSL

3. **`deploy/nginx.conf`** - Consider adding SSL configuration for Full mode

---

## Key Technical Details

### EC2 Instance
- IP: `3.22.127.222`
- User: `ubuntu`
- App directory: `~/receipt-ranger`
- Virtual env: `~/receipt-ranger/venv`

### Service Management
```bash
sudo systemctl status receipt-ranger   # Check status
sudo systemctl restart receipt-ranger  # Restart app
sudo systemctl status nginx            # Check Nginx
sudo nginx -t                          # Test Nginx config
```

### Useful Debugging Commands
```bash
# Check if Streamlit is listening
sudo ss -tlnp | grep :8501

# Check Nginx error logs
sudo tail -50 /var/log/nginx/receipt-ranger.error.log

# Test Nginx proxy locally
curl localhost        # Should return Streamlit HTML
curl localhost:8501   # Direct to Streamlit

# Check what IP domain resolves to
nslookup receipt-ranger.com
```

---

## After Deployment Is Successful

1. Merge branch to main
2. Bump version
3. Close CFS features/5
4. Update deploy/README.md with lessons learned

---

## Questions for Future Agent

1. Does setting up origin SSL with a self-signed cert fix the WebSocket issue?
2. If not, are there Cloudflare-specific WebSocket settings to check?
3. Could the issue be Cloudflare rate-limiting WebSocket connections? (Safari showed 429 errors)
