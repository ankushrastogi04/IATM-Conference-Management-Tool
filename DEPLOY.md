# How to Deploy IATM Conference Management Tool

A step-by-step guide to get the app running on a live server. No prior experience needed.

**Total time: ~25 minutes**

---

## Step 1: Get a Server (~5 min)

You need a **VPS** (Virtual Private Server) — a remote Linux machine that runs 24/7.

### Recommended providers:
| Provider | Price | Link |
|----------|-------|------|
| DigitalOcean | $6/mo | https://digitalocean.com |
| Hostinger VPS | $4/mo | https://hostinger.com |
| Linode (Akamai) | $5/mo | https://linode.com |

### What to select:
- **OS**: Ubuntu 24.04 LTS
- **Plan**: 1 CPU, 2GB RAM, 50GB disk (cheapest option is fine)
- **Region**: Closest to your users (US East for USA)
- **Authentication**: SSH key (recommended) or password

### After creating the server:
You'll get an **IP address** (e.g., `143.198.100.50`). Save it.

### Connect to your server:
Open your terminal (Mac/Linux) or PowerShell (Windows) and run:
```bash
ssh root@YOUR_SERVER_IP
```
Type `yes` when asked about fingerprint, then enter your password.

---

## Step 2: Install Docker (~5 min)

Run these commands **on the server** (copy-paste one at a time):

```bash
# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh

# Install Docker Compose plugin
apt install -y docker-compose-plugin

# Verify installation
docker --version
docker compose version
```

You should see version numbers printed. If not, something went wrong — try running the commands again.

---

## Step 3: Upload the Code (~3 min)

Still on the server, clone your repository:

```bash
cd /opt
git clone https://github.com/ankushrastogi04/IATM-Conference-Management-Tool.git
cd IATM-Conference-Management-Tool
```

---

## Step 4: Configure Environment (~5 min)

Create the production environment file:

```bash
nano "cmt project/.env"
```

Paste this content (edit the values marked with `<-- CHANGE`):

```env
# Django
DEBUG=False
SECRET_KEY=PASTE_A_LONG_RANDOM_STRING_HERE
ALLOWED_HOSTS=YOUR_SERVER_IP

# Database (these are used by both Django and PostgreSQL container)
DB_NAME=iatm_conference_db
DB_USER=iatm_user
DB_PASSWORD=PICK_A_STRONG_DB_PASSWORD_HERE
DB_HOST=db
DB_PORT=5432

# Email (Gmail — already working from dev)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=arastogitech@gmail.com
EMAIL_HOST_PASSWORD=pniu wdce pbcj kzae
DEFAULT_FROM_EMAIL=IATM Conference <arastogitech@gmail.com>

# PayPal
PAYPAL_PAYMENT_LINK=https://www.paypal.com/ncp/payment/GS5U6A4CU5P2A

# SSL (set to True AFTER completing Step 7)
ENABLE_SSL=False
```

**To generate a SECRET_KEY**, run this in another terminal:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```
Or use any random string generator — make it at least 50 characters.

**Save and exit**: Press `Ctrl+X`, then `Y`, then `Enter`.

---

## Step 5: Launch the App (~5 min)

```bash
# Build and start all services (Postgres + Django + Nginx)
docker compose -f docker-compose.prod.yml up -d --build
```

This will take 2-3 minutes the first time. You'll see logs scrolling — wait for it to finish.

**Check that everything is running:**
```bash
docker compose -f docker-compose.prod.yml ps
```

You should see 3 services: `db`, `web`, `nginx` — all with status `Up`.

**Create your admin account:**
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```
Enter your email, name, and password when prompted.

**Test it:** Open your browser and go to:
```
http://YOUR_SERVER_IP
```

You should see the IATM login page!

### If something went wrong:
```bash
# Check logs
docker compose -f docker-compose.prod.yml logs web
docker compose -f docker-compose.prod.yml logs nginx

# Restart everything
docker compose -f docker-compose.prod.yml restart
```

---

## Step 6: Set Up Backups (~2 min)

```bash
# Create backup directory
mkdir -p backups

# Run a test backup now
docker compose -f docker-compose.prod.yml exec db pg_dump -U iatm_user iatm_conference_db | gzip > backups/backup_$(date +%Y%m%d).sql.gz

# Verify backup was created
ls -la backups/
```

**Set up automatic daily backups** (runs every day at 2am):
```bash
crontab -e
```

Add this line at the bottom:
```
0 2 * * * cd /opt/IATM-Conference-Management-Tool && docker compose -f docker-compose.prod.yml exec -T db pg_dump -U iatm_user iatm_conference_db | gzip > backups/backup_$(date +\%Y\%m\%d).sql.gz && find backups/ -name "*.gz" -mtime +30 -delete
```

Save and exit.

---

## Step 7: Add a Domain + SSL (Optional, do later)

### 7a. Buy a domain
Buy a domain from [Namecheap](https://namecheap.com), [Google Domains](https://domains.google), or any registrar.

### 7b. Point domain to your server
In your domain's DNS settings, add:
- **Type**: A Record
- **Name**: @ (or your subdomain)
- **Value**: YOUR_SERVER_IP
- **TTL**: 300

Wait 5-10 minutes for DNS to propagate. Test with:
```bash
ping yourdomain.com
```

### 7c. Update ALLOWED_HOSTS
```bash
nano "cmt project/.env"
```
Change:
```
ALLOWED_HOSTS=YOUR_SERVER_IP,yourdomain.com,www.yourdomain.com
```

### 7d. Get SSL certificate (free via Let's Encrypt)

First, switch nginx to the SSL-ready config:
```bash
# Edit docker-compose.prod.yml
nano docker-compose.prod.yml
```
Change the nginx volume line from:
```
- ./deploy/nginx.conf:/etc/nginx/conf.d/default.conf:ro
```
to:
```
- ./deploy/nginx.prod.conf:/etc/nginx/conf.d/default.conf:ro
```

Update the domain in nginx config:
```bash
nano deploy/nginx.prod.conf
```
Replace `YOUR_DOMAIN` with your actual domain (2 places: `ssl_certificate` and `ssl_certificate_key`).

Now get the certificate:
```bash
# Restart with HTTP-only first so certbot can verify
docker compose -f docker-compose.prod.yml restart nginx

# Run certbot (replace YOUR_DOMAIN and YOUR_EMAIL)
docker compose -f docker-compose.prod.yml run --rm certbot certonly --webroot -w /var/www/certbot --email YOUR_EMAIL -d YOUR_DOMAIN --agree-tos --no-eff-email
```

### 7e. Enable SSL in Django
```bash
nano "cmt project/.env"
```
Change:
```
ENABLE_SSL=True
```

### 7f. Restart everything
```bash
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```

Your site should now be live at `https://yourdomain.com`!

### 7g. Auto-renew SSL (every 60 days)
```bash
crontab -e
```
Add:
```
0 3 1 */2 * cd /opt/IATM-Conference-Management-Tool && docker compose -f docker-compose.prod.yml run --rm certbot renew && docker compose -f docker-compose.prod.yml restart nginx
```

---

## Step 8: Ongoing Maintenance

### Update the app (after pushing new code to GitHub):
```bash
cd /opt/IATM-Conference-Management-Tool
git pull origin main
docker compose -f docker-compose.prod.yml up -d --build
```

### View logs:
```bash
# All services
docker compose -f docker-compose.prod.yml logs -f

# Just the Django app
docker compose -f docker-compose.prod.yml logs -f web

# Just nginx
docker compose -f docker-compose.prod.yml logs -f nginx
```

### Restart services:
```bash
docker compose -f docker-compose.prod.yml restart
```

### Open Django shell (for admin tasks):
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py shell
```

### Restore from backup:
```bash
gunzip < backups/backup_20260429.sql.gz | docker compose -f docker-compose.prod.yml exec -T db psql -U iatm_user iatm_conference_db
```

### Check disk space:
```bash
df -h
docker system df
```

### Clean up old Docker images:
```bash
docker system prune -f
```

---

## Verification Checklist

After deployment, test these:

- [ ] `http://YOUR_SERVER_IP` shows the login page
- [ ] Can register a new account
- [ ] Can login
- [ ] `/admin/` loads the Django admin panel
- [ ] `/api/` loads the API browser
- [ ] `/health/` returns `{"status": "ok"}`
- [ ] Conference page loads at `/conference/iatm-2026-fall/`
- [ ] Email works (try password reset)

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "502 Bad Gateway" | Django isn't ready yet. Wait 30s, or check `docker compose logs web` |
| "Connection refused" | Firewall blocking port 80. Run: `ufw allow 80 && ufw allow 443` |
| Static files not loading (ugly page) | Run: `docker compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput` then restart nginx |
| "CSRF verification failed" | Make sure `ALLOWED_HOSTS` in `.env` includes your domain/IP |
| Database error on first launch | Run: `docker compose -f docker-compose.prod.yml exec web python manage.py migrate` |
| Email not sending | Check `.env` has correct Gmail app password. Check logs for SMTP errors. |
| Can't login as admin | Create superuser: `docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser` |
| Site redirects to HTTPS but no SSL | Set `ENABLE_SSL=False` in `.env` and restart |

---

## Architecture Overview

```
                    Internet
                       |
                  Port 80/443
                       |
                   [ Nginx ]
                   /       \
          /static/         Everything else
          /media/              |
             |            [ Gunicorn ]
         (files)          (Python/Django)
                               |
                         [ PostgreSQL ]
                          (Database)
```

All 3 services run in Docker containers managed by Docker Compose.
