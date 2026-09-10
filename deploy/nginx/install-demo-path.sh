#!/usr/bin/env bash
set -euo pipefail

SITE=/etc/nginx/sites-available/my-blog
SNIPPET=/etc/nginx/snippets/ai-aegis-demo-location.conf
TEMPLATE=${1:-/opt/ai-aegis/current/deploy/nginx/aegis-demo-location.conf.template}
CREDENTIAL_FILE=/root/.ai-aegis-demo-credentials

if [[ ${EUID} -ne 0 ]]; then
    echo "Run as root." >&2
    exit 1
fi
if [[ ! -f $SITE ]]; then
    echo "Existing my-blog Nginx site not found." >&2
    exit 1
fi

backup=/root/my-blog-before-ai-aegis-$(date +%Y%m%d-%H%M%S).conf
cp -a "$SITE" "$backup"
install -o root -g root -m 0644 "$TEMPLATE" "$SNIPPET"
if [[ -f $CREDENTIAL_FILE ]]; then
    sed -i 's|^URL=.*|URL=https://goodevenin9.website/aegis/|' "$CREDENTIAL_FILE"
    chmod 0600 "$CREDENTIAL_FILE"
fi

if ! grep -qF 'include /etc/nginx/snippets/ai-aegis-demo-location.conf;' "$SITE"; then
    awk '
        /^[[:space:]]*error_page 404 \/404\.html;/ {
            print "    include /etc/nginx/snippets/ai-aegis-demo-location.conf;"
            print ""
        }
        { print }
    ' "$SITE" > "${SITE}.new"
    mv "${SITE}.new" "$SITE"
fi

nginx -t
systemctl reload nginx
echo "AI Aegis demo path installed; backup: $backup"
