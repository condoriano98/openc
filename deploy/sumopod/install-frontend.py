#!/usr/bin/env python3
"""Fetch a public frontend build; stage and verify it before switching releases."""
import hashlib
import json
from pathlib import Path
import re
import sys
import tarfile
import tempfile
import urllib.request

base = sys.argv[1].rstrip("/")
if not base.startswith("https://"):
    raise SystemExit("An HTTPS build URL is required")
root = Path(__file__).resolve().parent
with urllib.request.urlopen(base + "/_transfer/manifest.json", timeout=60) as response:
    manifest = json.load(response)
commit = manifest["commit"]
if not re.fullmatch(r"[0-9a-f]{40}", commit):
    raise SystemExit("Invalid build commit")
release = root / "frontend-releases" / commit
if not (release / "index.html").is_file():
    release.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="openc-frontend-") as temporary:
        archive = Path(temporary) / "frontend.tar.gz"
        with archive.open("wb") as output:
            for item in manifest["files"]:
                if not re.fullmatch(r"frontend.part-[0-9]+", item["name"]):
                    raise SystemExit("Invalid part name")
                digest = hashlib.sha256()
                part = Path(temporary) / item["name"]
                count = 0
                with urllib.request.urlopen(base + "/_transfer/" + item["name"], timeout=180) as source, part.open("wb") as target:
                    while chunk := source.read(1024 * 1024):
                        digest.update(chunk)
                        count += len(chunk)
                        target.write(chunk)
                if count != item["bytes"] or digest.hexdigest() != item["sha256"]:
                    raise SystemExit("Frontend download checksum mismatch")
                with part.open("rb") as source:
                    while chunk := source.read(1024 * 1024):
                        output.write(chunk)
                print("Verified", item["name"], flush=True)
        with tarfile.open(archive) as package:
            package.extractall(release, filter="data")
if not (release / "index.html").is_file() or not (release / "_app").is_dir():
    raise SystemExit("Incomplete frontend release")
link = root / "frontend"
if link.exists() and not link.is_symlink():
    raise SystemExit("frontend exists and is not a symlink; inspect it before migrating")
staged = root / "frontend.next"
staged.unlink(missing_ok=True)
staged.symlink_to(release, target_is_directory=True)
staged.replace(link)
print("FRONTEND_READY", commit)
