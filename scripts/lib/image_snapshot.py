"""Freeze local image identities without resolving or pulling mutable registry tags."""

import copy
import json
import re
import subprocess

from lib.compose_bundle import portable_networks


def inspect(reference):
    return json.loads(
        subprocess.check_output(["docker", "image", "inspect", reference], text=True)
    )[0]


def freeze(compose, inspector=inspect):
    result = copy.deepcopy(compose)
    portable_networks(result)
    images = {}
    for name, service in result["services"].items():
        reference = service["image"]
        metadata = inspector(reference)
        identity = metadata["Id"]
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", identity):
            raise ValueError("Missing immutable local image ID")
        if metadata["Os"] != "linux":
            raise ValueError("Full requires Linux images")
        images[name] = {
            "imageId": identity,
            "inputReference": reference,
            "repoDigests": metadata.get("RepoDigests", []),
            "os": metadata["Os"],
            "architecture": metadata["Architecture"],
            "variant": metadata.get("Variant", ""),
        }
        service.pop("build", None)
        service["image"] = identity
        service["pull_policy"] = "never"
        service["platform"] = "/".join(
            filter(
                None,
                (metadata["Os"], metadata["Architecture"], metadata.get("Variant")),
            )
        )
        for mount in service.get("volumes", []):
            if mount.get("source", "").startswith(
                ("${ZOMBIE_RUNTIME_ROOT", "${ZOMBIE_CORE_DIR")
            ):
                mount["type"] = "bind"
                mount.pop("volume", None)
                mount.setdefault("bind", {})["create_host_path"] = False
    if images["gateway"]["imageId"] != images["discovery"]["imageId"]:
        raise ValueError("Gateway/discovery must use the same image")
    if len({(v["os"], v["architecture"], v["variant"]) for v in images.values()}) != 1:
        raise ValueError("All local images must target the same platform")
    return result, images


def validate(manifest, inspector=inspect):
    missing = []
    for image in manifest["images"].values():
        identity = image["imageId"]
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", identity):
            raise ValueError("Invalid image lock")
        try:
            actual = inspector(identity)
        except subprocess.CalledProcessError:
            missing.append(identity)
            continue
        if any(
            actual[key] != image[field]
            for key, field in (
                ("Id", "imageId"),
                ("Os", "os"),
                ("Architecture", "architecture"),
            )
        ):
            raise ValueError("Loaded image differs from the frozen identity/platform")
        if actual.get("Variant", "") != image["variant"]:
            raise ValueError("Loaded image variant differs")
    return sorted(set(missing))
