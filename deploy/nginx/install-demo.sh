#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
    echo "Run as root." >&2
    exit 1
fi

ENV_FILE=${1:-/opt/ai-aegis/shared/.env.self-host}
SITE_TEMPLATE=${2:-/opt/ai-aegis/current/deploy/nginx/aegis-demo.conf.template}
CREDENTIAL_FILE=/root/.ai-aegis-demo-credentials
HTPASSWD_FILE=/etc/nginx/.htpasswd-ai-aegis
TOKEN_SNIPPET=/etc/nginx/snippets/ai-aegis-engine-token.conf
SITE_FILE=/etc/nginx/sites-available/ai-aegis-demo

engine_token=$(sed -n 's/^AEGIS_ENGINE_INGRESS_TOKEN=//p' "$ENV_FILE" | head -n 1)
if [[ ! $engine_token =~ ^[A-Za-z0-9._~-]{32,}$ ]]; then
    echo "Missing or invalid AEGIS_ENGINE_INGRESS_TOKEN." >&2
    exit 1
fi

if [[ ! -s $CREDENTIAL_FILE ]]; then
    dashboard_password=$(openssl rand -base64 30 | tr -d '\n' | tr '/+' '_-')
    umask 077
    printf 'URL=https://aegis.goodevenin9.website\nUSERNAME=aegis-demo\nPASSWORD=%s\n' \
        "$dashboard_password" > "$CREDENTIAL_FILE"
else
    dashboard_password=$(sed -n 's/^PASSWORD=//p' "$CREDENTIAL_FILE" | head -n 1)
fi

password_hash=$(openssl passwd -apr1 "$dashboard_password")
printf 'aegis-demo:%s\n' "$password_hash" > "$HTPASSWD_FILE"
chown root:www-data "$HTPASSWD_FILE"
chmod 0640 "$HTPASSWD_FILE"

install -d -m 0755 /etc/nginx/snippets
install -d -m 0755 /var/www/letsencrypt/.well-known/acme-challenge
printf 'proxy_set_header X-Api-Key "%s";\n' "$engine_token" > "$TOKEN_SNIPPET"
chown root:root "$TOKEN_SNIPPET"
chmod 0600 "$TOKEN_SNIPPET"

backup=/root/nginx-before-ai-aegis-$(date +%Y%m%d-%H%M%S).tar.gz
tar -C /etc -czf "$backup" nginx
install -o root -g root -m 0644 "$SITE_TEMPLATE" "$SITE_FILE"
ln -sfn "$SITE_FILE" /etc/nginx/sites-enabled/ai-aegis-demo

nginx -t
systemctl reload nginx
echo "AI Aegis demo Nginx site installed; backup: $backup"
