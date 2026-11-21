#!/usr/bin/env bash
# Ubuntu 24.04 x86_64. Run as root. See the usage printed below.
set -Eeuo pipefail
umask 077

app=/opt/aibrowser
lanes=(claude chatgpt)
displays=(99 100)
mcp_ports=(8931 8932)
vnc_ports=(5901 5902)
viewer_ports=(6081 6082)
backend=openc-backend-1
gateway=openc-gateway-1

die() { printf '%s\n' "$*" >&2; exit 1; }
[[ $EUID == 0 ]] || die 'Run this script with sudo.'
action=${1:-}
domain=${2:-browser.43.173.40.109.sslip.io}
[[ $domain =~ ^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$ && $domain == *.* ]] ||
  die 'Pass a DNS hostname such as browser.example.com.'

backup_openc() (
  local snapshot data
  install -d -m 700 /var/backups/openc
  snapshot=$(mktemp -d /var/backups/openc/snapshot.XXXXXXXX)
  data=$(docker volume inspect --format '{{.Mountpoint}}' openc_data)
  [[ -s $data/webui.db ]] || die 'OpenC database not found.'
  tar -C /home/ubuntu -czf "$snapshot/checkout.tar.gz" openc
  if [[ $(docker inspect --format '{{.State.Running}}' "$backend") == true ]]; then
    trap 'docker start "$backend" >/dev/null' EXIT
    docker stop "$backend" >/dev/null
  fi
  tar -C "$data" -czf "$snapshot/data.tar.gz" .
  tar -tzf "$snapshot/data.tar.gz" > "$snapshot/data-files.txt"
  grep -Fxq ./webui.db "$snapshot/data-files.txt"
  (cd "$snapshot" && sha256sum checkout.tar.gz data.tar.gz > SHA256SUMS && sha256sum -c SHA256SUMS)
  printf 'OpenC backup verified at %s\n' "$snapshot"
)

stage() {
  [[ $(uname -m) == x86_64 ]] || die 'This installer requires x86_64.'
  . /etc/os-release
  [[ $ID == ubuntu && $VERSION_ID == 24.04 ]] || die 'This installer requires Ubuntu 24.04.'
  install -d -m 755 "$app" "$app/mcp"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y --no-install-recommends ca-certificates curl openssl xz-utils \
    xvfb xauth x11-utils fluxbox x11vnc novnc websockify fonts-noto-core fonts-noto-color-emoji
  (
    tmp=$(mktemp -d)
    trap 'rm -rf -- "$tmp"' EXIT
    cd "$tmp"
    if [[ ! -x $app/node/bin/node ]]; then
      release=https://nodejs.org/dist/latest-v24.x
      curl -fsSL --retry 3 "$release/SHASUMS256.txt" -o sums
      archive=$(awk '$2 ~ /^node-v24\.[0-9]+\.[0-9]+-linux-x64\.tar\.xz$/ {print $2}' sums)
      [[ $archive =~ ^node-v24\.[0-9]+\.[0-9]+-linux-x64\.tar\.xz$ ]] || die 'Node archive not found.'
      curl -fsSL --retry 3 "$release/$archive" -o "$archive"
      awk -v name="$archive" '$2 == name' sums | sha256sum --check
      install -d -m 755 "$app/node"
      tar -xJf "$archive" --strip-components=1 --no-same-owner -C "$app/node"
    fi
    if ! command -v google-chrome >/dev/null; then
      curl -fsSL --retry 3 https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -o chrome.deb
      chmod 755 "$tmp"
      chmod 644 chrome.deb
      apt-get install -y --no-install-recommends "$tmp/chrome.deb"
    fi
    export PATH="$app/node/bin:$PATH"
    chmod 755 "$app/node"
    if [[ ! -f $app/mcp/package-lock.json ]]; then
      npm install --prefix "$app/mcp" --save-exact --ignore-scripts --no-audit --no-fund @playwright/mcp
    fi
    chmod -R a+rX "$app/mcp"
    docker cp "$gateway:/usr/bin/caddy" caddy
    install -m 755 caddy "$app/caddy"
  )
  id aib-caddy >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin aib-caddy
  for i in "${!lanes[@]}"; do
    local lane display account home mcp vnc novnc
    lane=${lanes[i]}
    display=${displays[i]}
    account=aib-$lane
    home=$app/$lane
    mcp=${mcp_ports[i]}
    vnc=${vnc_ports[i]}
    novnc=${viewer_ports[i]}
    id "$account" >/dev/null 2>&1 ||
      useradd --system --user-group --home-dir "$home" --shell /usr/sbin/nologin "$account"
    install -d -m 700 -o "$account" -g "$account" "$home" "$home/profile" "$home/work"
    [[ -s $home/Xauthority ]] ||
      runuser -u "$account" -- xauth -q -f "$home/Xauthority" add ":$display" . "$(openssl rand -hex 16)"
    unit "$lane" xvfb '' "/usr/bin/Xvfb :$display -screen 0 1280x800x24 -nolisten tcp -auth $home/Xauthority" \
      'ExecStartPost=/bin/sh -c "for i in $(seq 1 50); do /usr/bin/xdpyinfo >/dev/null 2>&1 && exit 0; sleep .2; done; exit 1"'
    unit "$lane" wm "ai-$lane-xvfb.service" /usr/bin/fluxbox
    unit "$lane" vnc "ai-$lane-xvfb.service" \
      "/usr/bin/x11vnc -display :$display -auth $home/Xauthority -rfbport $vnc -listen 127.0.0.1 -localhost -nopw -forever -shared -quiet"
    unit "$lane" novnc "ai-$lane-vnc.service" \
      "/usr/bin/websockify --web /usr/share/novnc 127.0.0.1:$novnc 127.0.0.1:$vnc"
    unit "$lane" mcp "ai-$lane-xvfb.service ai-$lane-wm.service" \
      "$app/node/bin/node $app/mcp/node_modules/@playwright/mcp/cli.js --browser chrome --sandbox --host 127.0.0.1 --port $mcp --user-data-dir $home/profile --viewport-size 1280,740 --shared-browser-context --ignore-roots --output-dir $home/work"
  done
  cat >/etc/systemd/system/ai-browser-caddy.service <<UNIT
[Unit]
Description=HTTPS for the AI browser lanes
After=network-online.target
Wants=network-online.target

[Service]
User=aib-caddy
Group=aib-caddy
StateDirectory=ai-browser-caddy
Environment=HOME=/var/lib/ai-browser-caddy
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
NoNewPrivileges=true
ExecStart=$app/caddy run --config $app/Caddyfile --adapter caddyfile
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT
  chmod 644 /etc/systemd/system/ai-*.service
  systemctl daemon-reload
  systemctl restart ai-{claude,chatgpt}-{mcp,novnc}.service
  printf 'Both lanes are staged on loopback. Run smoke next.\n'
}

unit() {
  local name=$1 service=$2 deps=$3 command=$4 extra=${5:-}
  cat >"/etc/systemd/system/ai-$name-$service.service" <<UNIT
[Unit]
Description=AI browser $name $service
After=$deps
BindsTo=$deps

[Service]
User=$account
Group=$account
Environment=DISPLAY=:$display XAUTHORITY=$home/Xauthority HOME=$home PATH=$app/node/bin:/usr/local/bin:/usr/bin:/bin
WorkingDirectory=$home/work
UMask=0077
ProtectHome=true
ProtectSystem=strict
ReadWritePaths=$home /tmp
ExecStart=$command
$extra
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
UNIT
}

smoke() (
  # Free the RAM OpenC will release at cutover. Restore it even if either test fails.
  if [[ $(docker inspect --format '{{.State.Running}}' "$backend") == true ]]; then
    trap 'docker start "$backend" >/dev/null' EXIT
    docker stop "$backend" >/dev/null
  fi
  python3 - <<'PY'
import concurrent.futures
import json
import urllib.request

def probe(port, viewer):
    url = f'http://127.0.0.1:{port}/mcp'
    with urllib.request.urlopen(f'http://127.0.0.1:{viewer}/vnc.html', timeout=10) as res:
        assert b'noVNC' in res.read(), 'noVNC page unavailable'
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'}

    def rpc(method, params, request_id=None):
        body = dict(jsonrpc='2.0', method=method, params=params)
        if request_id is not None:
            body['id'] = request_id
        req = urllib.request.Request(url, json.dumps(body).encode(), headers)
        with urllib.request.urlopen(req, timeout=75) as res:
            if res.headers.get('Mcp-Session-Id'):
                headers['Mcp-Session-Id'] = res.headers['Mcp-Session-Id']
            if res.status == 202:
                return {}
            if res.headers.get_content_type() == 'text/event-stream':
                for line in res:
                    if line.startswith(b'data: '):
                        result = json.loads(line[6:])
                        break
                else:
                    raise RuntimeError('MCP stream ended before a response')
            else:
                result = json.load(res)
        if 'error' in result:
            raise RuntimeError(result['error'])
        return result['result']

    init = rpc('initialize', {
        'protocolVersion': '2025-06-18', 'capabilities': {},
        'clientInfo': {'name': 'vps-smoke-test', 'version': '1'},
    }, 1)
    headers['MCP-Protocol-Version'] = init['protocolVersion']
    rpc('notifications/initialized', {})
    try:
        page = rpc('tools/call', {'name': 'browser_navigate', 'arguments': {'url': 'https://example.com/'}}, 2)
        assert not page.get('isError') and 'Example Domain' in json.dumps(page), page
        print(f'MCP {port}: Chrome navigated to Example Domain, noVNC page served', flush=True)
    finally:
        rpc('tools/call', {'name': 'browser_close', 'arguments': {}}, 3)

with concurrent.futures.ThreadPoolExecutor(2) as pool:
    tests = [pool.submit(probe, 8931, 6081), pool.submit(probe, 8932, 6082)]
    for test in tests:
        test.result()
PY
  free -m
)

configure() {
  local pass confirmation hash tmp secret name i
  [[ -t 0 ]] || die 'Set the viewer password in the interactive VPS console.'
  read -rsp 'Viewer password (16 to 72 bytes): ' pass
  printf '\n'
  read -rsp 'Repeat viewer password: ' confirmation
  printf '\n'
  [[ $pass == "$confirmation" && ${#pass} -ge 16 && ${#pass} -le 72 ]] ||
    die 'Use matching passwords of 16 to 72 characters.'
  hash=$(printf '%s' "$pass" | "$app/caddy" hash-password)
  unset pass confirmation
  tmp=$(mktemp "$app/Caddyfile.XXXXXXXX")
  install -d -m 700 "$app/keys"
  {
    printf '{\n    admin off\n}\n%s {\n    header Referrer-Policy no-referrer\n' "$domain"
    for i in "${!lanes[@]}"; do
      name=${lanes[i]}
      [[ -s $app/keys/$name ]] || openssl rand -hex 32 > "$app/keys/$name"
      read -r secret < "$app/keys/$name"
      [[ $secret =~ ^[a-f0-9]{64}$ ]] || die 'Malformed connector token.'
      cat <<CFG
    handle /$secret/mcp {
        rewrite * /mcp
        reverse_proxy 127.0.0.1:${mcp_ports[i]} {
            header_up Host 127.0.0.1:${mcp_ports[i]}
            flush_interval -1
        }
    }
    handle_path /view-$name/* {
        basicauth {
            iman $hash
        }
        reverse_proxy 127.0.0.1:${viewer_ports[i]} {
            header_up -Authorization
        }
    }
CFG
    done
    printf '    respond 404\n}\n'
  } > "$tmp"
  "$app/caddy" validate --config "$tmp" --adapter caddyfile > "$app/validate.log" 2>&1 ||
    die "Caddy configuration failed validation. Check $app/validate.log privately."
  install -m 640 -o root -g aib-caddy "$tmp" "$app/Caddyfile"
  rm -f -- "$tmp"
  {
    for name in "${lanes[@]}"; do
      read -r secret < "$app/keys/$name"
      printf '[%s]\nConnector: https://%s/%s/mcp\nViewer: https://%s/view-%s/vnc.html?path=view-%s/websockify&autoconnect=1&resize=scale\n\n' \
        "$name" "$domain" "$secret" "$domain" "$name" "$name"
    done
  } > "$app/SECRETS.txt"
  printf '%s\n' "$domain" > "$app/domain"
  printf 'Viewer password configured for iman. Connector URLs are in %s/SECRETS.txt.\n' "$app"
}

publish() (
  [[ -s $app/Caddyfile && -s $app/domain ]] || die 'Run configure first.'
  read -r domain < "$app/domain"
  [[ $(getent ahostsv4 "$domain" | awk 'NR == 1 {print $1}') == 43.173.40.109 ]] ||
    die 'The browser hostname does not resolve to the Sumopod VPS.'
  backup_openc
  trap 'systemctl disable --now ai-browser-caddy.service >/dev/null 2>&1 || true; docker start "$backend" "$gateway" >/dev/null' EXIT
  docker stop "$backend" "$gateway" >/dev/null
  systemctl enable --now ai-{claude,chatgpt}-{mcp,novnc}.service ai-browser-caddy.service
  for attempt in {1..30}; do
    claude_status=$(curl --silent --max-time 3 --output /dev/null --write-out '%{http_code}' "https://$domain/view-claude/vnc.html" || true)
    chatgpt_status=$(curl --silent --max-time 3 --output /dev/null --write-out '%{http_code}' "https://$domain/view-chatgpt/vnc.html" || true)
    if [[ $claude_status == 401 && $chatgpt_status == 401 ]]; then
      trap - EXIT
      printf 'Both public viewers require authentication at https://%s. OpenC containers are stopped.\n' "$domain"
      exit 0
    fi
    sleep 2
  done
  die 'HTTPS or viewer authentication failed. Restoring OpenC.'
)

case "$action" in
  backup) backup_openc ;;
  stage) stage ;;
  smoke) smoke ;;
  configure) configure ;;
  publish) publish ;;
  *) die "Usage: sudo bash setup.sh {backup|stage|smoke|configure [hostname]|publish}" ;;
esac
