# SFLL — League Management System — Deployment Guide

## Docker Quickstart

The fastest way to get running locally:

```bash
# 1. Clone the repo
git clone https://github.com/sfll-org/league-management-system.git
cd league-management-system

# 2. Copy environment config
cp .env.example .env
# Edit .env if needed (defaults work for local dev)

# 3. Start all services
docker compose up -d

# 4. Create your admin user
docker compose exec web python manage.py createsuperuser

# 5. Open the app
open http://localhost:8001
```

This starts five containers:
- **web** — Django app (port 8001)
- **db** — PostgreSQL 16 (port 5433)
- **redis** — Redis 7 (port 6380)
- **celery-worker** — Background task processor
- **celery-beat** — Scheduled task scheduler

### Stopping

```bash
docker compose down          # Stop containers (keep data)
docker compose down -v       # Stop containers + destroy volumes (full reset)
```

### Rebuilding after code changes

```bash
docker compose build web
docker compose up -d
```

---

## Configuration Reference

All configuration is via environment variables in `.env`. See `.env.example` for the full list with comments.

### Required Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key. Generate a real one for production. | insecure dev key |
| `DEBUG` | Enable debug mode. **Must be `False` in production.** | `True` |
| `ALLOWED_HOSTS` | Comma-separated hostnames. | `localhost,127.0.0.1` |
| `DATABASE_URL` | PostgreSQL connection string. | `postgresql://sfll:dev_password@db:5432/sfll` |
| `REDIS_URL` | Redis connection for cache + Channels. | `redis://redis:6379/1` |
| `CELERY_BROKER_URL` | Celery message broker. | `redis://redis:6379/0` |
| `CELERY_RESULT_BACKEND` | Celery result store. | `redis://redis:6379/0` |

### Port Mapping (Docker)

| Variable | Host Port | Container Port | Purpose |
|----------|-----------|----------------|---------|
| `DB_PORT` | 5433 | 5432 | PostgreSQL |
| `REDIS_PORT` | 6380 | 6379 | Redis |
| `WEB_PORT` | 8001 | 8000 | Django |

### Email

| Variable | Description |
|----------|-------------|
| `EMAIL_BACKEND` | `django.core.mail.backends.console.EmailBackend` (dev) or `django.core.mail.backends.smtp.EmailBackend` (prod) |
| `EMAIL_HOST` | SMTP server hostname |
| `EMAIL_PORT` | SMTP port (typically 587 for TLS) |
| `EMAIL_HOST_USER` | SMTP username |
| `EMAIL_HOST_PASSWORD` | SMTP password |
| `EMAIL_USE_TLS` | `True` for TLS |
| `DEFAULT_FROM_EMAIL` | Sender address |

---

## Production Setup

### Prerequisites

- Docker and Docker Compose (or a VM with Python 3.12, PostgreSQL 16, Redis 7)
- A domain name with DNS pointing to your server
- SSL certificate (Let's Encrypt recommended)

### 1. Gunicorn

The Docker image uses Gunicorn by default:

```bash
gunicorn sfll.wsgi:application --bind 0.0.0.0:8000 --workers 2
```

For production, tune workers based on CPU count:

```bash
gunicorn sfll.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
```

### 2. Nginx Reverse Proxy

Example nginx configuration:

```nginx
server {
    listen 80;
    server_name sfll.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name sfll.example.com;

    ssl_certificate /etc/letsencrypt/live/sfll.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/sfll.example.com/privkey.pem;

    client_max_body_size 10M;

    location /static/ {
        alias /app/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /app/media/;
        expires 7d;
    }

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 3. SSL with Let's Encrypt

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d sfll.example.com
```

### 4. Production `.env` Checklist

```env
SECRET_KEY=<generate-a-real-key>
DEBUG=False
ALLOWED_HOSTS=sfll.example.com
DATABASE_URL=postgresql://sfll:<strong-password>@db:5432/sfll
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=noreply@sfll.org
EMAIL_HOST_PASSWORD=<smtp-password>
DEFAULT_FROM_EMAIL=SFLL <noreply@sfll.org>
```

---

## Admin Setup

### Creating the First User

```bash
# Via Docker
docker compose exec web python manage.py createsuperuser

# Without Docker
python manage.py createsuperuser
```

Follow the prompts to set email, first name, last name, and password.

### Configuring the League

1. Log in to the Django admin at `/admin/`
2. Create a **League** record (e.g., name: "San Francisco Little League", short_name: "SFLL")
3. Create **Divisions** (e.g., Majors, AAA, AA, A, Rookie) with appropriate display orders
4. Create **Stations** for evaluations (e.g., Hitting, Infield, Outfield, Pitching) with eval_fields JSON
5. Create a **Season** and mark it as active

### Assigning CTO Role

The first superuser can access all admin features. To grant CTO access to non-superuser accounts:

1. Go to the User Management page (`/admin/users/`)
2. Find the user and click "Roles"
3. Add the "CTO / Admin" role for your league

### Station eval_fields Format

Each station's `eval_fields` is a JSON array of field definitions:

```json
[
    {"key": "arm_strength", "label": "Arm Strength", "type": "integer", "min": 1, "max": 5},
    {"key": "accuracy", "label": "Accuracy", "type": "integer", "min": 1, "max": 5},
    {"key": "footwork", "label": "Footwork", "type": "integer", "min": 1, "max": 5}
]
```

Supported types: `integer`, `decimal`, `boolean`, `text`.

---

## Health Check

The app exposes a health check endpoint at `/healthz` (no auth required):

```bash
curl http://localhost:8001/healthz
# {"status": "ok"}
```

Docker Compose uses this for container health monitoring.
