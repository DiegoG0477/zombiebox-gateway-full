"""Keep generated Compose defaults relocatable between installation projects."""


def portable_networks(compose):
    # `compose config` materializes the source project's generated network name.
    # Keeping it would silently attach a candidate to the existing installation.
    project = compose.get("name")
    if not project:
        return
    for key, network in compose.get("networks", {}).items():
        if not network.get("external") and network.get("name") == f"{project}_{key}":
            network.pop("name")
