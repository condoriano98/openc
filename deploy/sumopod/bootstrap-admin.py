#!/usr/bin/env python3
"""Run on the VPS as ubuntu; enter credentials directly at the console."""
import getpass
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request
import urllib.error

os.chdir(Path(__file__).resolve().parents[2])
command = ["sudo", "docker", "compose", "-f", "deploy/sumopod/compose.yaml"]
email = input("OpenC admin email: ").strip()
password = getpass.getpass("Choose OpenC admin password (hidden): ")
confirmation = getpass.getpass("Confirm password (hidden): ")
if "@" not in email or len(password) < 12 or password != confirmation:
    raise SystemExit("Email invalid, password shorter than 12 characters, or passwords differ. Run again.")
# sudo preserves only these explicitly selected environment variables.
env = os.environ | {"WEBUI_ADMIN_EMAIL": email, "WEBUI_ADMIN_PASSWORD": password}
bootstrap = ["sudo", "--preserve-env=WEBUI_ADMIN_EMAIL,WEBUI_ADMIN_PASSWORD",
             "docker", "compose", "-f", "deploy/sumopod/compose.yaml",
             "up", "-d", "--force-recreate", "backend"]
print("Creating the first admin locally...")
subprocess.run(bootstrap, env=env, check=True)
payload = json.dumps({"email": email, "password": password}).encode()
success = False
for attempt in range(60):
    try:
        request = urllib.request.Request(
            "http://127.0.0.1:8080/api/v1/auths/signin",
            data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=3) as response:
            result = json.load(response)
        success = bool(result.get("token"))
        break
    except urllib.error.HTTPError:
        time.sleep(2)
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        time.sleep(2)
# Recreate without the bootstrap credentials; admin hash and session secret persist in the volume.
clean_env = {key: value for key, value in os.environ.items()
             if key not in {"WEBUI_ADMIN_EMAIL", "WEBUI_ADMIN_PASSWORD"}}
subprocess.run(command + ["up", "-d", "--force-recreate", "backend"],
               env=clean_env, check=True)
if not success:
    raise SystemExit("Admin login could not be verified. Backend remains private; inspect logs.")
print("ADMIN_SETUP_OK: admin login verified; bootstrap password removed from container configuration.")
