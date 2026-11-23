#!/usr/bin/env bash
set -eu
umask 077
app=/opt/aibrowser
cd "$app"
workspace=workspace.jiwati.com
old=$(cat domain)
[[ $old =~ ^[A-Za-z0-9.-]+$ ]]
case "${1:-stage}" in
  stage)
    install -d -m 755 /var/www/jiwati-workspace
    umask 022
    cat > /var/www/jiwati-workspace/index.html <<'HTML'
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Jiwati Workspace</title>
<style>
:root{color-scheme:light;--ink:#202e38;--muted:#4e616d;--accent:#1b655e;--line:#d6e0db}
*{box-sizing:border-box}
body{margin:0;background:#eef3ef;color:var(--ink);font:1rem/1.55 system-ui,sans-serif;padding:clamp(1rem,6vw,5rem)}
main{max-width:42rem;margin:6vh auto;background:#fff;border:1px solid var(--line);border-radius:1rem;padding:clamp(1.4rem,6vw,3rem)}
h1{font-size:clamp(2rem,7vw,3.25rem);letter-spacing:-.04em;line-height:1.1;margin:0}
p{color:var(--muted);max-width:35ch}
nav{display:grid;grid-template-columns:repeat(auto-fit,minmax(11rem,1fr));gap:.7rem;margin-top:2rem}
a{display:block;padding:.9rem 1rem;color:var(--accent);border:1px solid var(--line);border-radius:.55rem;text-decoration:none;font-weight:650}
a:hover,a:focus-visible{background:#e8f4ef;text-decoration:underline}
</style>
</head>
<body>
<main>
<h1>Jiwati Workspace</h1>
<p>Choose a private browser viewer and sign in with your workspace credentials.</p>
<nav aria-label="Private browser viewers">
<a href="/view-a/vnc.html?path=view-a/websockify&amp;autoconnect=1&amp;resize=scale">Open Viewer A</a>
<a href="/view-b/vnc.html?path=view-b/websockify&amp;autoconnect=1&amp;resize=scale">Open Viewer B</a>
</nav>
</main>
</body>
</html>
HTML
    umask 077
    python3 - "$old" "$workspace" <<'PY'
from pathlib import Path
import re
import sys
old, workspace = sys.argv[1:]
config = Path("Caddyfile").read_text()
if workspace in config:
    raise SystemExit("Workspace already appears in the active configuration.")
header = re.compile(r"^" + re.escape(old) + r"\s*\{$", re.MULTILINE)
if len(header.findall(config)) != 1:
    raise SystemExit("Could not identify the existing viewer site block.")
new = """%s, %s {
    @workspaceIndex {
        host %s
        path /
    }
    handle @workspaceIndex {
        header X-Robots-Tag "noindex, nofollow"
        root * /var/www/jiwati-workspace
        file_server
    }
""" % (old, workspace, workspace)
Path("Caddyfile.workspace").write_text(header.sub(new.rstrip(), config, count=1))
PY
    ./caddy validate --config Caddyfile.workspace --adapter caddyfile > workspace-validation.log 2>&1
    printf '%s\n' 'Workspace configuration validated. Current HTTPS unchanged.'
    ;;
  activate)
    cp -p Caddyfile Caddyfile.before-workspace
    recover() {
      cp -p Caddyfile.before-workspace Caddyfile
      systemctl restart ai-browser-caddy
    }
    cat Caddyfile.workspace > Caddyfile
    if ! systemctl restart ai-browser-caddy; then
      recover
      exit 1
    fi
    for try in $(seq 1 15); do
      workspace_status=$(curl -s --max-time 4 -o /dev/null -w '%{http_code}' "https://$workspace/" || true)
      old_status=$(curl -s --max-time 4 -o /dev/null -w '%{http_code}' "https://$old/view-a/vnc.html" || true)
      a_status=$(curl -s --max-time 4 -o /dev/null -w '%{http_code}' "https://$workspace/view-a/vnc.html" || true)
      b_status=$(curl -s --max-time 4 -o /dev/null -w '%{http_code}' "https://$workspace/view-b/vnc.html" || true)
      if [ "$workspace_status:$old_status:$a_status:$b_status" = '200:401:401:401' ]; then
        printf '%s\n' 'Workspace HTTPS works. Both viewers need sign-in. Original address still works.'
        exit 0
      fi
      sleep 2
    done
    printf '%s\n' 'Workspace could not be verified. Restoring the previous configuration.' >&2
    recover
    exit 1
    ;;
  *) exit 2 ;;
esac
