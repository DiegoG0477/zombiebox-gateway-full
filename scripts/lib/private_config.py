"""Private JSON persistence; helpers never log configuration values."""

import json


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def ensure_config(path, defaults):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.exists():
        write_json(path, defaults)
    return json.loads(path.read_text())


def configure_provider(providers, name, url, token, enable):
    if len(token) < 32:
        raise ValueError(f"Invalid {name} worker token; existing file preserved")
    if name not in providers:
        providers[name] = {"enabled": enable, "url": url, "token": token}
    elif enable:
        providers[name]["enabled"] = True
