---
github_issue: 16
---
# AWS Deployment Handoff Document

## Working directory

`~/Desktop/receipt-ranger`

## Contents

**Date:** 2026-02-04
**Branch:** `feature/aws-deployment`
**CFS Issue:** features/5 (GitHub #11)
**Status:** Documentation complete, awaiting manual deployment

---

## Summary

This session created comprehensive AWS deployment documentation for Receipt Ranger. The infrastructure code and guides are ready; the actual deployment to AWS needs to be performed manually by the user.

## What Was Completed

### Files Created

| File | Purpose |
|------|---------|
| `deploy/README.md` | Step-by-step AWS deployment guide |
| `deploy/nginx.conf` | Nginx reverse proxy configuration (replace `YOUR-DOMAIN.COM`) |
| `deploy/receipt-ranger.service` | Systemd service file for auto-restart |
| `requirements.txt` | Python dependencies for pip install |

### Files Modified

| File | Changes |
|------|---------|
| `.streamlit/config.toml` | Added production settings (headless, XSRF, address binding) |
| `.gitignore` | Added `logs/` directory |
| `app.py` | Updated version footer to v0.5.0 |
| `README.md` | Added Deployment section |

### Commit

- **Hash:** `b49f49e`
- **Message:** `feat: Add AWS deployment documentation and production configuration`

---

## What Remains To Be Done

The user needs to manually perform the deployment following `deploy/README.md`:

### Phase 1: AWS EC2 Setup
- [ ] Launch Ubuntu 22.04 EC2 instance (t2.micro or t3.small)
- [ ] Configure security group (SSH, HTTP, HTTPS)
- [ ] Create and download key pair
- [ ] Allocate Elastic IP
- [ ] Set up billing alerts

### Phase 2: Server Configuration
- [ ] SSH into instance
- [ ] Install Python 3.10+, pip, venv
- [ ] Install Nginx
- [ ] Configure Nginx using `deploy/nginx.conf` (update domain name)
- [ ] Create www user for Nginx security
- [ ] Start and enable Nginx

### Phase 3: CloudFlare Setup
- [ ] Register/add domain in CloudFlare
- [ ] Create A record pointing to Elastic IP
- [ ] Enable proxy mode (orange cloud) for DDoS protection
- [ ] Configure SSL (Flexible mode recommended for simplicity)
- [ ] Enable "Always Use HTTPS"

### Phase 4: Deploy Application
- [ ] Upload application files (git clone or SFTP)
- [ ] Create virtual environment
- [ ] Install dependencies from `requirements.txt`
- [ ] Copy `service_account.json` for Google Sheets (optional)
- [ ] Test application manually
- [ ] Set up auto-start (cron or systemd)

### Phase 5: Security Hardening (Recommended)
- [ ] Configure UFW firewall
- [ ] Install fail2ban
- [ ] Enable unattended-upgrades

---

## After Deployment Is Successful

Once the site is live and working:

1. **Merge the branch:**
   ```bash
   git checkout main
   git merge feature/aws-deployment
   git push
   ```

2. **Bump version:**
   ```bash
   bump2version minor  # 0.5.0 -> 0.6.0
   ```

3. **Close CFS issue:**
   ```bash
   cfs i features complete 5 --force
   ```

---

## Key Technical Details

### Architecture
```
User (Phone/Browser)
        │
        ▼
   CloudFlare (DNS + SSL + DDoS Protection)
        │
        ▼
   AWS EC2 (Ubuntu)
        │
        ├── Nginx (Port 80, reverse proxy)
        │       │
        │       ▼
        └── Streamlit (Port 8501)
```

### Security Model
- **API Keys:** Users provide their own via the web UI (BYOAPI model)
- **Keys are stored only in session memory, never persisted**
- **DDoS Protection:** CloudFlare proxy mode absorbs attacks
- **SSL:** Handled by CloudFlare (no cert management on server)

### Important Files on Server
- `/etc/nginx/nginx.conf` - Nginx configuration
- `/etc/systemd/system/receipt-ranger.service` - Service definition
- `~/receipt-ranger/` - Application directory
- `~/receipt-ranger/service_account.json` - Google Sheets credentials (sensitive)

### Troubleshooting Commands
```bash
# Check if Streamlit is running
ps aux | grep streamlit

# View Streamlit logs
cat ~/streamlit.log  # or journalctl -u receipt-ranger if using systemd

# Check Nginx status
sudo systemctl status nginx
sudo tail -f /var/log/nginx/error.log

# Restart services
sudo systemctl restart nginx
sudo systemctl restart receipt-ranger
```

---

## User Preferences Noted

- User prefers **vim** over nano for text editing
- User works in infrastructure and wants hands-on AWS learning experience
- User chose AWS EC2 over simpler options (Streamlit Cloud) for learning purposes

---

## Questions for Future Agent

If the user returns with deployment issues, common areas to investigate:

1. **502 Bad Gateway** - Streamlit not running or crashed
2. **WebSocket errors** - Nginx config missing upgrade headers
3. **SSL issues** - CloudFlare proxy mode not enabled
4. **App won't start on reboot** - Cron or systemd misconfigured

