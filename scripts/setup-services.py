#!/usr/bin/env python3
"""Prepare private optional services and pinned source-only build contexts."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import tarfile
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument("--enable", choices=("spotify", "airplay", "threadfin", "rebrowser"))
parser.add_argument("--sources", action="store_true")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
os.umask(0o077)

def write(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)

provider_file = root / ".local/gateway/config/providers.json"
providers = json.loads(provider_file.read_text())
browser_folder = root / ".local/rebrowser"
browser_folder.mkdir(parents=True, exist_ok=True)
browser_config = browser_folder / "browser.json"
if not browser_config.exists():
    write(browser_config, {"token": secrets.token_hex(32)})
if "rebrowser" not in providers:
    providers["rebrowser"] = {"enabled": args.enable == "rebrowser", "url": "http://rebrowser:8094", "token": json.loads(browser_config.read_text())["token"]}
elif args.enable == "rebrowser":
    providers["rebrowser"]["enabled"] = True
for name, port in (("spotify", 8092), ("airplay", 8093)):
    folder = root / ".local" / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "state").mkdir(exist_ok=True)
    worker = folder / "worker.json"
    if not worker.exists():
        config = {"mode": name, "listen": f"0.0.0.0:{port}", "token": secrets.token_hex(32), "stateDir": "/state"}
        if name == "airplay":
            config["pin"] = f"{secrets.randbelow(10000):04d}"
        write(worker, config)
    config = json.loads(worker.read_text())
    if len(config.get("token", "")) < 32:
        raise SystemExit(f"Invalid {name} worker token; existing file preserved")
    host = "host.docker.internal" if name == "airplay" else name
    if name not in providers:
        providers[name] = {"enabled": args.enable == name, "url": f"http://{host}:{port}", "token": config["token"]}
    elif args.enable == name:
        providers[name]["enabled"] = True
    if name == "spotify":
        daemon = folder / "state/config.yml"
        if not daemon.exists():
            daemon.write_text("""device_name: Zombie Box Spotify
device_type: speaker
credentials:
  type: device_auth
zeroconf_enabled: false
audio_backend: pipe
audio_output_pipe: /state/audio.pcm
audio_output_pipe_format: s16le
audio_output_pipe_wait_for_reader: true
volume_steps: 100
initial_volume: 75
server:
  enabled: true
  address: 127.0.0.1
  port: 3678
""")
        daemon.chmod(0o600)
    folder.chmod(0o700)
    (folder / "state").chmod(0o700)
    worker.chmod(0o600)

(root / ".local/threadfin").mkdir(exist_ok=True)
if args.enable == "threadfin":
    current = providers.get("iptv", {})
    if current.get("url") and "/m3u/threadfin.m3u" not in current["url"]:
        raise SystemExit("Existing IPTV input preserved. Import it in Threadfin and explicitly select the Threadfin export in gateway settings.")
    providers["iptv"] = {"enabled": True, "url": "http://threadfin:34400/m3u/threadfin.m3u", "epgUrl": "http://threadfin:34400/xmltv/threadfin.xml"}
write(provider_file, providers)

if args.sources:
    lock = json.loads((root / "third_party/upstreams.lock.json").read_text())
    for entry in lock["repositories"]:
        if entry["name"] not in ("go-librespot", "uxplay", "threadfin"):
            continue
        source = root / "third_party/sources" / entry["name"]
        actual = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
        if actual != entry["commit"]:
            raise SystemExit(f"Restore pinned {entry['name']} with make references")
        destination = root / ".local/build-sources" / entry["name"]
        destination.mkdir(parents=True, exist_ok=True)
        # git archive excludes local changes, .git and untracked generated files.
        with tempfile.TemporaryFile() as archive:
            subprocess.run(["git", "-C", str(source), "archive", actual], stdout=archive, check=True)
            archive.seek(0)
            with tarfile.open(fileobj=archive) as content:
                content.extractall(destination, filter="data")
        (destination / "ZOMBIE_UPSTREAM_COMMIT").write_text(actual + "\n")
print("Optional service configuration prepared; secrets and existing provider inputs preserved.")
