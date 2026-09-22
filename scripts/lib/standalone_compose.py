"""Compose-native Full initialization: named volumes and no host toolchain/config files."""

import copy

from lib.compose_bundle import portable_networks

MOUNTS = {
    "gateway": {
        "/data": "gateway-state",
        "/media": "media",
        "/probes": "probes",
        "/config": "gateway",
    },
    "youtube": {"/config": "youtube"},
    "youtube-receiver": {"/config": "youtube-receiver"},
    "spotify": {"/config/worker.json": "spotify", "/state": "spotify-state"},
    "airplay": {"/config/worker.json": "airplay", "/state": "airplay-state"},
    "threadfin": {"/state": "threadfin-state"},
    "rebrowser": {"/config/browser.json": "rebrowser"},
    "mediamtx": {"/mediamtx.yml": "mediamtx"},
}


def standalone(compose, bootstrap_image):
    result = copy.deepcopy(compose)
    portable_networks(result)
    result["name"] = "zombie-full"
    result["volumes"] = {
        name: {} for mounts in MOUNTS.values() for name in mounts.values()
    }
    for name, service in result["services"].items():
        service.pop("build", None)
        if name == "discovery":
            continue
        service.setdefault("depends_on", {})["initialize"] = {
            "condition": "service_completed_successfully"
        }
        mounts = []
        for mount in service.get("volumes", []):
            target = mount["target"]
            source = MOUNTS[name][target]
            if target in {
                "/config/worker.json",
                "/config/browser.json",
                "/mediamtx.yml",
            }:
                target = "/config"
            mounts.append(
                {
                    "type": "volume",
                    "source": source,
                    "target": target,
                    "read_only": mount.get("read_only", False),
                }
            )
        service["volumes"] = mounts
    gateway = result["services"]["gateway"]
    gateway["entrypoint"] = ["/bin/sh", "/config/launch.sh"]
    gateway["environment"].pop("ZOMBIE_RELAY_ADMIN_TOKEN", None)
    gateway["environment"].pop("ZOMBIE_PAIRING_CODE", None)
    result["services"]["youtube"].pop("profiles", None)
    relay = result["services"]["mediamtx"]
    relay["environment"].pop("MTX_AUTHHTTPADDRESS", None)
    relay["command"] = ["/config/mediamtx.yml"]
    browser = result["services"]["rebrowser"]
    browser["security_opt"] = [
        value for value in browser["security_opt"] if not value.startswith("seccomp=")
    ]
    browser["security_opt"].append("seccomp=./seccomp.json")
    result["services"]["initialize"] = {
        "image": bootstrap_image,
        "user": "0:0",
        "network_mode": "none",
        "environment": {
            "ZOMBIE_UID": "${ZOMBIE_UID:-1000}",
            "ZOMBIE_GID": "${ZOMBIE_GID:-1000}",
        },
        "volumes": [
            {"type": "volume", "source": name, "target": "/seed/" + name}
            for name in sorted(result["volumes"])
        ],
        "read_only": True,
        "tmpfs": ["/tmp:size=1048576,mode=1777"],
        "cap_drop": ["ALL"],
        "cap_add": ["CHOWN", "DAC_OVERRIDE", "FOWNER"],
        "security_opt": ["no-new-privileges:true"],
        "mem_limit": "96m",
        "cpus": 0.5,
        "pids_limit": 16,
        "restart": "no",
    }
    return result
