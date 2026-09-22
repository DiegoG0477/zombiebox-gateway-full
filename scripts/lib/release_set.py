"""Release-time identity checks; installation never resolves a moving version."""

import copy
import re


def release_version(value):
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+(?:-[a-zA-Z0-9.-]+)?", value):
        raise ValueError("Use an explicit ZombieBox release version, never latest")
    return value


def registry_set(compose, images):
    if set(images) != set(compose["services"]):
        raise ValueError(
            "Every service, including initialize and MediaMTX, needs a registry digest"
        )
    if images["gateway"] != images["discovery"]:
        raise ValueError("Gateway/discovery images must match")
    result = copy.deepcopy(compose)
    for name, reference in images.items():
        if not re.fullmatch(r"[a-z0-9][a-z0-9./:_-]+@sha256:[a-f0-9]{64}", reference):
            raise ValueError("Registry deployment requires immutable manifest digests")
        result["services"][name]["image"] = reference
    return result
