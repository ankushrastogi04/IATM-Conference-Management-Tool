# How to Deploy IATM Conference Management Tool

A step-by-step guide to deploy the app to **conference.iatm.us** using a Hostinger VPS.

**Total time: ~30 minutes**

---

## Overview

```
You already have:
  iatm.us ──> Hostinger Website Builder (your existing websites)

What we're setting up:
  conference.iatm.us ──> Hostinger VPS (new, $4-6/mo) ──> Docker ──> Conference App
```

Your existing websites on iatm.us will NOT be affected.

---

## Step 1: Buy a Hostinger VPS (~5 min)

This is separate from your existing Hostinger website builder plan.

1. Go to https://www.hostinger.com/vps-hosting
2. Pick the cheapest plan (**KVM 1** — 1 vCPU, 4GB RAM, ~$5/mo)
3. During setup, select:
   - **OS**: Ubuntu 22.04 or 24.04
   - **Server location**: USA (closest to conference attendees)
   - **Root password**: Pick a strong password and **save it somewhere safe**
4. After purchase, go to **hPanel** → **VPS** → your new VPS
5. Find your **VPS IP address** (e.g., `154.38.100.50`) — **write it down**

---

## Step 2: Point conference.iatm.us to the VPS (~5 min)

1. Go to **Hostinger hPanel** → **Domains** → **iatm.us** → **DNS / Nameservers** → **DNS Records**
2. Click **Add Record** and fill in:

   | Field | Value |
   |-------|-------|
   | Type | A |
   | Name | conference |
   | Points to | YOUR_VPS_IP (e.g., 154.38.100.50) |
   | TTL | 300 |

3. Click **Add Record**
4. Wait 5-10 minutes for DNS to propagate
5. Verify it works — open your terminal and run:
   ```bash
   ping conference.iatm.us
   ```
   You should see your VPS IP in the response.

---

## Step 3: Connect to Your VPS (~2 min)

Open **Terminal** (Mac) or **PowerShell** (Windows) on your computer:

```bash
ssh root@YOUR_VPS_IP
```

- Type `yes` when asked about the fingerprint
- Enter the root password you set in Step 1

You're now on your server! All commands from here run **on the server**.

---

## Step 4: Install Docker (~5 min)

Copy-paste these commands one at a time:

```bash
# Update the system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh

# Install Docker Compose plugin
apt install -y docker-compose-plugin

# Verify it worked
docker --version
docker compose version
```

You should see version numbers. If you get errors, run each command again.

---

## Step 5: Download the Code (~2 min)

```bash
cd /opt
git clone https://github.com/ankushrastogi04/IATM-Conference-Management-Tool.git
cd IATM-Conference-Management-Tool
```

---

## Step 6: Create the Environment File (~5 min)

This file contains all your passwords and settings. It is NOT uploaded to GitHub.

```bash
nano "cmt project/.env"
```

Paste this entire block, then edit the 3 lines marked with `# <-- CHANGE THIS`:

```env
# Django
DEBUG=False
SECRET_KEY=PASTE_YOUR_SECRET_KEY_HERE                    # <-- CHANGE THIS
ALLOWED_HOSTS=conference.iatm.us,YOUR_VPS_IP             # <-- CHANGE THIS (put your real VPS IP)

# Database
DB_NAME=iatm_conference_db
DB_USER=iatm_user
DB_PASSWORD=PICK_A_STRONG_PASSWORD_HERE                  # <-- CHANGE THIS
DB_HOST=db
DB_PORT=5432

# Email (Gmail SMTP)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=arastogitech@gmail.com
EMAIL_HOST_PASSWORD=YOUR_GMAIL_APP_PASSWORD_HERE              # <-- CHANGE THIS
DEFAULT_FROM_EMAIL=IATM Conference <arastogitech@gmail.com>

# PayPal
PAYPAL_PAYMENT_LINK=https://www.paypal.com/ncp/payment/GS5U6A4CU5P2A

# SSL (we'll enable this in Step 9)
ENABLE_SSL=False
```

### How to generate a SECRET_KEY:

Run this on your **local machine** (not the server):
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```
Copy the output and paste it as the SECRET_KEY value.

If you don't have Python, use any random string generator — make it at least 50 characters long.

### Save the file:
- Press `Ctrl + X`
- Press `Y` to confirm
- Press `Enter` to save

---

## Step 7: Open Firewall Ports (~1 min)

```bash
# Allow web traffic
ufw allow 22    # SSH (so you don't lock yourself out!)
ufw allow 80    # HTTP
ufw allow 443   # HTTPS
ufw enable      # Turn on firewall
```

Type `y` when asked to confirm.

---

## Step 8: Launch the App (~5 min)

```bash
cd /opt/IATM-Conference-Management-Tool

# Build and start everything (this takes 2-3 minutes the first time)
docker compose -f docker-compose.prod.yml up -d --build
```

Wait for it to finish. Then check that all services are running:

```bash
docker compose -f docker-compose.prod.yml ps
```

You should see 3 services all showing **Up**:
```
NAME       SERVICE   STATUS
...-db-1   db        Up (healthy)
...-web-1  web       Up
...-nginx  nginx     Up
```

### Create your admin account:
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

Enter when prompted:
- **Email**: ankushrastogi04@gmail.com
- **First name**: Ankush
- **Last name**: Rastogi
- Other fields as you like
- **Password**: Pick a strong one

### Test it!

Open your browser and go to:
```
http://conference.iatm.us
```

You should see the IATM login page! If DNS hasn't propagated yet, try:
```
http://YOUR_VPS_IP
```

---

## Step 9: Add Free SSL Certificate (~5 min)

This gives you HTTPS (the lock icon in the browser). Free via Let's Encrypt.

### 9a. Get the certificate:
```bash
cd /opt/IATM-Conference-Management-Tool

# Get SSL certificate (replace YOUR_EMAIL with your email)
docker compose -f docker-compose.prod.yml run --rm certbot certonly --webroot -w /var/www/certbot --email ankushrastogi04@gmail.com -d conference.iatm.us --agree-tos --no-eff-email
```

If successful, you'll see "Congratulations!" in the output.

### 9b. Switch nginx to HTTPS config:
```bash
nano docker-compose.prod.yml
```

Find the line:
```
      - ./deploy/nginx.conf:/etc/nginx/conf.d/default.conf:ro
```

Change it to:
```
      - ./deploy/nginx.prod.conf:/etc/nginx/conf.d/default.conf:ro
```

Save and exit (`Ctrl+X`, `Y`, `Enter`).

### 9c. Update the nginx config with your domain:
```bash
nano deploy/nginx.prod.conf
```

Find these two lines (near the top of the HTTPS block):
```
    ssl_certificate     /etc/letsencrypt/live/YOUR_DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/YOUR_DOMAIN/privkey.pem;
```

Replace `YOUR_DOMAIN` with `conference.iatm.us` in BOTH lines:
```
    ssl_certificate     /etc/letsencrypt/live/conference.iatm.us/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/conference.iatm.us/privkey.pem;
```

Save and exit.

### 9d. Enable SSL in Django:
```bash
nano "cmt project/.env"
```

Change:
```
ENABLE_SSL=True
```

Save and exit.

### 9e. Restart everything:
```bash
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```

### 9f. Test it!

Go to: **https://conference.iatm.us**

You should see the lock icon and the login page!

### 9g. Set up auto-renewal (SSL expires every 90 days):
```bash
crontab -e
```

If asked which editor, choose `1` (nano). Add this line at the bottom:
```
0 3 1 */2 * cd /opt/IATM-Conference-Management-Tool && docker compose -f docker-compose.prod.yml run --rm certbot renew && docker compose -f docker-compose.prod.yml restart nginx
```

Save and exit. This automatically renews SSL every 2 months.

---

## Step 10: Set Up Daily Backups (~2 min)

```bash
# Create backup directory
mkdir -p /opt/IATM-Conference-Management-Tool/backups

# Test a backup now
cd /opt/IATM-Conference-Management-Tool
docker compose -f docker-compose.prod.yml exec -T db pg_dump -U iatm_user iatm_conference_db | gzip > backups/backup_$(date +%Y%m%d).sql.gz

# Verify it was created
ls -lh backups/
```

Set up automatic daily backups at 2am:
```bash
crontab -e
```

Add this line at the bottom (below the SSL renewal line if you added one):
```
0 2 * * * cd /opt/IATM-Conference-Management-Tool && docker compose -f docker-compose.prod.yml exec -T db pg_dump -U iatm_user iatm_conference_db | gzip > backups/backup_$(date +\%Y\%m\%d).sql.gz && find backups/ -name "*.gz" -mtime +30 -delete
```

Save and exit. Old backups are automatically deleted after 30 days.

---

## Verification Checklist

After completing all steps, test these:

- [ ] https://conference.iatm.us shows the login page with lock icon
- [ ] Can register a new account
- [ ] Can login with your admin account
- [ ] https://conference.iatm.us/admin/ loads Django admin panel
- [ ] https://conference.iatm.us/api/ loads the API browser
- [ ] https://conference.iatm.us/health/ returns `{"status": "ok"}`
- [ ] https://conference.iatm.us/conference/iatm-2026-fall/ shows the conference
- [ ] Password reset sends an email (test email delivery)
- [ ] Payment checkout redirects to PayPal

---

## How to Update the App (after making code changes)

Whenever you push changes to GitHub, update the live server:

```bash
ssh root@YOUR_VPS_IP
cd /opt/IATM-Conference-Management-Tool
git pull origin main
docker compose -f docker-compose.prod.yml up -d --build
```

That's it — the app rebuilds and restarts automatically.

---

## Useful Commands Reference

```bash
# Go to the project directory
cd /opt/IATM-Conference-Management-Tool

# Check if everything is running
docker compose -f docker-compose.prod.yml ps

# View logs (live)
docker compose -f docker-compose.prod.yml logs -f

# View just Django app logs
docker compose -f docker-compose.prod.yml logs -f web

# Restart everything
docker compose -f docker-compose.prod.yml restart

# Stop everything
docker compose -f docker-compose.prod.yml down

# Start everything
docker compose -f docker-compose.prod.yml up -d

# Open Django shell
docker compose -f docker-compose.prod.yml exec web python manage.py shell

# Create another admin user
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser

# Restore from backup
gunzip < backups/backup_20260508.sql.gz | docker compose -f docker-compose.prod.yml exec -T db psql -U iatm_user iatm_conference_db

# Check disk space
df -h

# Clean up old Docker images
docker system prune -f
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Can't connect via SSH | Check VPS is running in Hostinger hPanel. Check IP is correct. |
| "502 Bad Gateway" | Django is still starting. Wait 30 seconds, refresh. Check: `docker compose -f docker-compose.prod.yml logs web` |
| "Connection refused" | Firewall is blocking. Run: `ufw allow 80 && ufw allow 443` |
| Page looks ugly (no CSS) | Run: `docker compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput` then `docker compose -f docker-compose.prod.yml restart nginx` |
| "CSRF verification failed" | Check `ALLOWED_HOSTS` in `.env` includes `conference.iatm.us` |
| "DisallowedHost" error | Same as above — add your domain/IP to `ALLOWED_HOSTS` |
| Database error | Run: `docker compose -f docker-compose.prod.yml exec web python manage.py migrate` |
| Email not sending | Check Gmail app password in `.env`. Check logs: `docker compose -f docker-compose.prod.yml logs web` |
| SSL certificate failed | Make sure DNS points to VPS IP. Wait 10 min and try certbot again. |
| Site redirects to HTTPS but no SSL | Set `ENABLE_SSL=False` in `.env` and restart |
| Forgot admin password | Create new: `docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser` |

---

## Architecture

```
    Users visit conference.iatm.us
                 |
           DNS (Hostinger)
                 |
         Hostinger VPS (Ubuntu)
                 |
          Docker Compose
         /       |       \
      Nginx   Gunicorn   PostgreSQL
      (web     (Django     (database)
     server)    app)
```

- **Nginx**: Handles web requests, serves static files (CSS/images), provides SSL
- **Gunicorn**: Runs the Python/Django application
- **PostgreSQL**: Stores all data (users, conferences, papers, reviews, etc.)

All 3 run in Docker containers. Docker Compose manages them together.

---

## Monthly Cost

| Item | Cost |
|------|------|
| Hostinger VPS (KVM 1) | ~$5/mo |
| Domain (iatm.us) | Already owned |
| SSL certificate | Free (Let's Encrypt) |
| **Total** | **~$5/mo** |
