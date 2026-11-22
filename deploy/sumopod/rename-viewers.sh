#!/usr/bin/env bash
set -euo pipefail
umask 077
cd /opt/aibrowser
backup=$(mktemp -d ./viewer-path-backup.XXXXXXXX)
cp -p Caddyfile SECRETS.txt "$backup/"
rename() {
  sed -e 's/view-claude/view-a/g' -e 's/view-chatgpt/view-b/g' "$1"
}
rename Caddyfile > "$backup/new"
./caddy validate --config "$backup/new" --adapter caddyfile > "$backup/validation" 2>&1
restore() {
  cp -p "$backup/Caddyfile" "$backup/SECRETS.txt" .
  systemctl restart ai-browser-caddy
}
trap restore ERR
cat "$backup/new" > Caddyfile
systemctl restart ai-browser-caddy
domain=$(cat domain)
for path in view-a view-b; do
  status=$(curl -sS --retry 3 --retry-connrefused --max-time 8 -o /dev/null -w '%{http_code}' "https://$domain/$path/vnc.html")
  [[ $status == 401 ]]
done
rename "$backup/SECRETS.txt" > SECRETS.txt
trap - ERR
printf 'Both neutral viewer routes require authentication.\n'
