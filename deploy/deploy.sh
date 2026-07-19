#!/usr/bin/env sh

set -eu

APP_DIR="/var/www/KimiagarKhune"
REPO_URL="https://github.com/hsdarestani/KimiagarKhune.git"
DOMAIN="panel.kimiagarkhoone.com"
SERVER_IP="109.122.250.125"
ENV_FILE="/etc/kimiagarkhune.env"
SERVICE_NAME="kimiagarkhune"
DB_NAME="kimiagar_db"
DB_USER="kimiagar_user"

export DEBIAN_FRONTEND=noninteractive

if ! command -v apt-get >/dev/null 2>&1; then
    echo "This deploy script currently supports Ubuntu/Debian servers only."
    exit 1
fi

echo "==> Installing system packages"
apt-get update
apt-get install -y \
    ca-certificates \
    certbot \
    curl \
    default-libmysqlclient-dev \
    git \
    build-essential \
    mysql-server \
    nginx \
    openssl \
    pkg-config \
    python3 \
    python3-certbot-nginx \
    python3-dev \
    python3-pip \
    python3-venv

systemctl enable --now mysql
systemctl enable --now nginx

echo "==> Updating application source"
mkdir -p "$(dirname "$APP_DIR")"

if [ ! -d "$APP_DIR/.git" ]; then
    rm -rf "$APP_DIR"
    git clone "$REPO_URL" "$APP_DIR"
else
    git config --global --add safe.directory "$APP_DIR" || true
    git -C "$APP_DIR" fetch --prune origin main
fi

git -C "$APP_DIR" checkout -B main origin/main
git -C "$APP_DIR" reset --hard origin/main

echo "==> Creating Python virtual environment"
if [ ! -x "$APP_DIR/venv/bin/python" ]; then
    python3 -m venv "$APP_DIR/venv"
fi

"$APP_DIR/venv/bin/pip" install --upgrade pip setuptools wheel
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"

echo "==> Creating persistent environment configuration"
if [ ! -f "$ENV_FILE" ]; then
    DJANGO_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(64))')"
    DB_PASSWORD="$(openssl rand -hex 24)"

    cat > "$ENV_FILE" <<EOF
DJANGO_SETTINGS_MODULE=config.production
DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY
ALLOWED_HOSTS=$DOMAIN,$SERVER_IP,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://$DOMAIN
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD
DB_HOST=127.0.0.1
DB_PORT=3306
USE_HTTPS=0
TELEGRAM_BOT_TOKEN=
TELEGRAM_WORKER_URL=
KAVENEGAR_API_KEY=
KAVENEGAR_SENDER=
EOF
fi

# Update optional integration credentials from GitHub Secrets when supplied.
ENV_FILE="$ENV_FILE" python3 - <<'PY'
import os
from pathlib import Path

path = Path(os.environ["ENV_FILE"])
lines = path.read_text(encoding="utf-8").splitlines()

updates = {
    "TELEGRAM_BOT_TOKEN": os.environ.get("DEPLOY_TELEGRAM_BOT_TOKEN", ""),
    "TELEGRAM_WORKER_URL": os.environ.get("DEPLOY_TELEGRAM_WORKER_URL", ""),
    "KAVENEGAR_API_KEY": os.environ.get("DEPLOY_KAVENEGAR_API_KEY", ""),
    "KAVENEGAR_SENDER": os.environ.get("DEPLOY_KAVENEGAR_SENDER", ""),
}

for key, value in updates.items():
    if not value:
        continue
    if "\n" in value or "\r" in value:
        raise SystemExit(f"Secret {key} contains an unsupported newline")

    prefix = f"{key}="
    replacement = f"{key}={value}"
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = replacement
            break
    else:
        lines.append(replacement)

path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

chown root:www-data "$ENV_FILE"
chmod 640 "$ENV_FILE"

set -a
. "$ENV_FILE"
set +a

echo "==> Preparing MySQL"
mysql <<SQL
CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\`
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost'
    IDENTIFIED BY '${DB_PASSWORD}';
ALTER USER '${DB_USER}'@'localhost'
    IDENTIFIED BY '${DB_PASSWORD}';
GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.*
    TO '${DB_USER}'@'localhost';
FLUSH PRIVILEGES;
SQL

echo "==> Running Django deployment steps"
mkdir -p "$APP_DIR/media" "$APP_DIR/staticfiles"
cd "$APP_DIR"

"$APP_DIR/venv/bin/python" manage.py check
"$APP_DIR/venv/bin/python" manage.py migrate --noinput
"$APP_DIR/venv/bin/python" manage.py collectstatic --noinput

chown -R www-data:www-data "$APP_DIR/media" "$APP_DIR/staticfiles"

echo "==> Configuring systemd"
cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=KimiagarKhune Gunicorn service
After=network.target mysql.service
Requires=mysql.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENV_FILE
RuntimeDirectory=$SERVICE_NAME
RuntimeDirectoryMode=0755
ExecStart=$APP_DIR/venv/bin/gunicorn --workers 3 --timeout 120 --access-logfile - --error-logfile - --capture-output --bind unix:/run/$SERVICE_NAME/gunicorn.sock config.wsgi:application
Restart=always
RestartSec=5
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

echo "==> Configuring Nginx"
write_http_nginx() {
    cat > "/etc/nginx/sites-available/$SERVICE_NAME" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;

    client_max_body_size 50M;

    location /static/ {
        alias $APP_DIR/staticfiles/;
        expires 30d;
        access_log off;
    }

    location /media/ {
        alias $APP_DIR/media/;
        expires 7d;
    }

    location / {
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 60;
        proxy_read_timeout 120;
        proxy_send_timeout 120;
        proxy_pass http://unix:/run/$SERVICE_NAME/gunicorn.sock;
    }
}
EOF
}

write_https_nginx() {
    cat > "/etc/nginx/sites-available/$SERVICE_NAME" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name $DOMAIN;

    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;

    client_max_body_size 50M;

    location /static/ {
        alias $APP_DIR/staticfiles/;
        expires 30d;
        access_log off;
    }

    location /media/ {
        alias $APP_DIR/media/;
        expires 7d;
    }

    location / {
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_connect_timeout 60;
        proxy_read_timeout 120;
        proxy_send_timeout 120;
        proxy_pass http://unix:/run/$SERVICE_NAME/gunicorn.sock;
    }
}
EOF
}

ln -sfn "/etc/nginx/sites-available/$SERVICE_NAME" "/etc/nginx/sites-enabled/$SERVICE_NAME"
rm -f /etc/nginx/sites-enabled/default

if [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    write_https_nginx
else
    write_http_nginx
fi

nginx -t
systemctl reload nginx

if [ ! -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ] && [ -n "${DEPLOY_SSL_EMAIL:-}" ]; then
    echo "==> Requesting Let's Encrypt certificate"
    if certbot certonly --nginx \
        --non-interactive \
        --agree-tos \
        --email "$DEPLOY_SSL_EMAIL" \
        -d "$DOMAIN"; then
        write_https_nginx
        sed -i 's/^USE_HTTPS=.*/USE_HTTPS=1/' "$ENV_FILE"
        nginx -t
        systemctl reload nginx
        systemctl restart "$SERVICE_NAME"
    else
        echo "SSL certificate was not issued. The HTTP deployment remains active."
    fi
elif [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    sed -i 's/^USE_HTTPS=.*/USE_HTTPS=1/' "$ENV_FILE"
    systemctl restart "$SERVICE_NAME"
fi

systemctl --no-pager --full status "$SERVICE_NAME" || true
curl --fail --silent --show-error --max-time 20 \
    -H "Host: $DOMAIN" \
    http://127.0.0.1/ >/dev/null || true

echo "Deployment finished: https://$DOMAIN"
