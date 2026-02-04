# Receipt Ranger - AWS Deployment Guide

This guide walks through deploying Receipt Ranger to AWS EC2 with CloudFlare for DNS/SSL.

## Architecture Overview

```
User (Phone/Browser)
        │
        ▼
   CloudFlare (DNS + SSL + DDoS Protection)
        │
        ▼
   AWS EC2 (Ubuntu)
        │
        ├── Nginx (Reverse Proxy, Port 80)
        │       │
        │       ▼
        └── Streamlit (Port 8501)
```

## Prerequisites

- AWS Account (free tier eligible)
- CloudFlare Account (free)
- Domain name (purchase via CloudFlare ~$10/year for .com)
- Local copy of this repository
- `service_account.json` for Google Sheets integration (optional)

---

## Phase 1: AWS EC2 Setup

### 1.1 Launch EC2 Instance

1. Go to [AWS Console](https://aws.amazon.com/console/) and sign in
2. Navigate to **EC2** > **Instances** > **Launch Instance**

3. Configure the instance:
   - **Name**: `receipt-ranger`
   - **AMI**: Ubuntu Server 22.04 LTS (Free tier eligible)
   - **Instance type**: `t2.micro` (Free tier) or `t3.small` (better performance, ~$15/month)
   - **Key pair**: Create new, name it `receipt-ranger-key`, download the `.pem` file

4. **Network settings** - Click "Edit" and configure:
   - Allow SSH traffic from: My IP (more secure) or Anywhere (if IP changes)
   - Allow HTTPS traffic from the internet: ✓
   - Allow HTTP traffic from the internet: ✓

5. **Storage**: 20-30 GB gp2 (Free tier includes 30GB)

6. Click **Launch Instance**

### 1.2 Allocate Elastic IP (Recommended)

This prevents your IP from changing on instance restarts.

1. Go to **EC2** > **Elastic IPs** > **Allocate Elastic IP address**
2. Click **Allocate**
3. Select the new IP > **Actions** > **Associate Elastic IP address**
4. Select your `receipt-ranger` instance
5. Click **Associate**

**Note your Elastic IP** - you'll need it for CloudFlare DNS.

### 1.3 Set Up Billing Alerts

Protect yourself from unexpected charges:

1. Go to **Billing** > **Budgets** > **Create budget**
2. Choose "Cost budget"
3. Set monthly budget to $20 (or your preferred limit)
4. Add email alerts at 50%, 80%, 100%

### 1.4 Connect to Your Instance

```bash
# Set correct permissions on key file
chmod 400 ~/Downloads/receipt-ranger-key.pem

# Connect via SSH (replace YOUR_ELASTIC_IP)
ssh -i ~/Downloads/receipt-ranger-key.pem ubuntu@YOUR_ELASTIC_IP
```

---

## Phase 2: Server Configuration

Run these commands after SSH-ing into your instance.

### 2.1 Update System

```bash
sudo apt update && sudo apt upgrade -y
```

### 2.2 Install Python and Dependencies

```bash
# Install Python 3.10+ and pip
sudo apt install -y python3 python3-pip python3-venv

# Verify installation
python3 --version  # Should be 3.10+
```

### 2.3 Install Nginx

```bash
sudo apt install -y nginx
```

### 2.4 Configure Nginx

```bash
# Backup default config
sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup

# Create new config
sudo vim /etc/nginx/nginx.conf
```

**Paste the contents of `deploy/nginx.conf` from this repository** (replace `YOUR-DOMAIN.COM` with your actual domain).

Save and exit: Press `Esc`, then type `:wq`, then `Enter`.

### 2.5 Create www User for Nginx

```bash
sudo adduser --system --no-create-home --shell /bin/false --group --disabled-login www
```

### 2.6 Test and Start Nginx

```bash
# Test configuration
sudo nginx -t

# Start Nginx
sudo systemctl start nginx
sudo systemctl enable nginx  # Start on boot
```

---

## Phase 3: CloudFlare DNS and SSL

### 3.1 Register/Add Domain

1. Go to [CloudFlare](https://dash.cloudflare.com/) and sign in
2. Either:
   - **Register new domain**: Domain Registration > Register Domains
   - **Add existing domain**: Add a Site > Enter your domain

### 3.2 Configure DNS

1. Go to your domain > **DNS** > **Records**
2. Click **Add Record**:
   - **Type**: A
   - **Name**: @ (or your subdomain, e.g., `receipts`)
   - **IPv4 address**: Your EC2 Elastic IP
   - **Proxy status**: Proxied (orange cloud) - **Important for DDoS protection**
   - **TTL**: Auto

3. (Optional) Add www subdomain:
   - **Type**: CNAME
   - **Name**: www
   - **Target**: your-domain.com
   - **Proxy status**: Proxied

### 3.3 Configure SSL

1. Go to **SSL/TLS** > **Overview**
2. Set encryption mode to **Flexible** (easiest) or **Full** (more secure, requires more setup)

   > **Flexible**: CloudFlare handles SSL, traffic to your server is HTTP
   > **Full**: Requires SSL cert on your server (more complex)

3. Go to **SSL/TLS** > **Edge Certificates**
4. Enable **Always Use HTTPS**: On
5. Enable **Automatic HTTPS Rewrites**: On

### 3.4 (Recommended) Enable Rate Limiting

1. Go to **Security** > **WAF** > **Rate limiting rules**
2. Create a rule:
   - **Name**: Protect receipt uploads
   - **If incoming requests match**: URI Path contains `/`
   - **Rate limit**: 100 requests per 10 seconds
   - **Action**: Block for 1 minute

---

## Phase 4: Deploy Application

### 4.1 Upload Application Files

**Option A: Clone from GitHub** (if repo is public or you set up deploy keys)
```bash
cd ~
git clone https://github.com/YOUR_USERNAME/receipt-ranger.git
cd receipt-ranger
```

**Option B: Upload via SFTP** (using FileZilla or command line)
```bash
# From your LOCAL machine
scp -i ~/Downloads/receipt-ranger-key.pem -r /path/to/receipt-ranger ubuntu@YOUR_ELASTIC_IP:~/
```

### 4.2 Set Up Python Environment

```bash
cd ~/receipt-ranger

# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 4.3 Configure Google Sheets (Optional)

If you want Google Sheets integration:

```bash
# From your LOCAL machine, upload the service account file
scp -i ~/Downloads/receipt-ranger-key.pem /path/to/service_account.json ubuntu@YOUR_ELASTIC_IP:~/receipt-ranger/

# On the server, set correct permissions
chmod 600 ~/receipt-ranger/service_account.json
```

### 4.4 Test the Application

```bash
cd ~/receipt-ranger
source venv/bin/activate

# Run Streamlit (test mode)
streamlit run app.py
```

You should see output like:
```
You can now view your Streamlit app in your browser.
Network URL: http://0.0.0.0:8501
```

Press `Ctrl+C` to stop.

### 4.5 Set Up Auto-Start on Reboot

**Option A: Cron (Simple)**

```bash
crontab -e
```

Add this line at the bottom (select vim as editor if prompted):
```
@reboot cd ~/receipt-ranger && source venv/bin/activate && streamlit run app.py --server.headless true > ~/streamlit.log 2>&1 &
```

**Option B: Systemd Service (More Robust)**

```bash
# Create logs directory
mkdir -p ~/receipt-ranger/logs

# Copy the service file
sudo cp ~/receipt-ranger/deploy/receipt-ranger.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start the service
sudo systemctl enable receipt-ranger
sudo systemctl start receipt-ranger

# Check status
sudo systemctl status receipt-ranger
```

### 4.6 Reboot and Test

```bash
sudo reboot
```

Wait 1-2 minutes, then visit your domain in a browser. The app should be running!

---

## Phase 5: Security Hardening (Recommended)

### 5.1 Configure UFW Firewall

```bash
# Enable UFW
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https
sudo ufw enable

# Verify
sudo ufw status
```

### 5.2 Install Fail2ban (SSH Protection)

```bash
sudo apt install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### 5.3 Keep System Updated

Set up automatic security updates:
```bash
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

---

## Troubleshooting

### App not loading
```bash
# Check if Streamlit is running
ps aux | grep streamlit

# Check Streamlit logs
cat ~/streamlit.log

# Check Nginx logs
sudo tail -f /var/log/nginx/error.log
```

### 502 Bad Gateway
- Streamlit isn't running or crashed
- Check if port 8501 is in use: `sudo lsof -i :8501`

### SSL Certificate Issues
- Make sure CloudFlare proxy is enabled (orange cloud)
- Try "Flexible" SSL mode first

### Can't SSH
- Check security group allows SSH from your IP
- Verify key file permissions: `chmod 400 your-key.pem`

---

## Maintenance

### View Logs
```bash
# Streamlit logs
tail -f ~/streamlit.log

# Nginx access logs
sudo tail -f /var/log/nginx/access.log

# Nginx error logs
sudo tail -f /var/log/nginx/error.log
```

### Update Application
```bash
cd ~/receipt-ranger
git pull  # If using git
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart receipt-ranger  # Or kill and restart if using cron
```

### Restart Services
```bash
sudo systemctl restart nginx
sudo systemctl restart receipt-ranger
```

---

## Cost Estimate

| Resource | Free Tier | After Free Tier |
|----------|-----------|-----------------|
| EC2 t2.micro | 750 hrs/month for 12 months | ~$8/month |
| Elastic IP | Free while attached | $3.65/month if unattached |
| Data transfer | 100GB/month | $0.09/GB |
| CloudFlare | Always free | - |
| Domain | - | ~$10/year |

**Estimated monthly cost after free tier**: $8-15/month
