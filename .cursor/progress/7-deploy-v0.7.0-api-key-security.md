---
github_issue: 34
---
# Deploy v0.7.0 — API Key Security Upgrade

## What changed

Version 0.7.0 introduces Fernet-encrypted API key storage and 7-day browser cookie persistence. The following are **required** on the production server before the app will work correctly:

1. New Python dependencies: `cryptography` and `streamlit-cookies-controller`
2. New environment variable: `SESSION_SECRET`

---

## Deployment steps

### 1. SSH into the EC2 instance

```bash
ssh -i ~/Secrets/receipt-ranger-key.pem ubuntu@3.22.127.222
```

### 2. Pull the new code

```bash
cd ~/receipt-ranger && git pull origin main
```

### 3. Install new dependencies

```bash
pip install cryptography>=41.0.0 "streamlit-cookies-controller>=0.0.4"
```

### 4. Generate and set SESSION_SECRET

Generate a key (run this once, save the output):

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Add it to the `.env` file on the server:

```bash
nano ~/receipt-ranger/.env
```

Find the `SESSION_SECRET=` line (already present from this branch) and paste in the generated key:

```
SESSION_SECRET=<paste-key-here>
```

> **Important:** Once set, do not change `SESSION_SECRET`. Changing it will invalidate all existing user cookies, requiring everyone to re-enter their API keys.

### 5. Restart the service

```bash
sudo systemctl restart receipt-ranger
```

### 6. Verify

```bash
sudo systemctl status receipt-ranger
```

Then open the app in a browser, enter an API key, and confirm:
- The `rr_session` and `rr_provider` cookies appear in browser DevTools → Application → Cookies
- After refreshing, the key and provider are restored without re-entry
- Receipt processing works with both OpenAI and Anthropic keys

---

## Rollback

If something goes wrong, revert to the previous release commit and restart:

```bash
git checkout ccb243a && sudo systemctl restart receipt-ranger
```

---

## Notes

- The `SESSION_SECRET` only needs to be set once. A random key is auto-generated if it's missing (fine for local dev), but production needs a stable key for cookies to survive server restarts.
- Cookies expire after 7 days — users are prompted to re-enter their key after that.
- No database or migration changes; this is a pure in-memory + cookie change.
