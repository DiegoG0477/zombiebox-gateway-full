# Linux LAN onboarding

The default Compose stack publishes gateway TCP8090 on all host interfaces and
starts a small credential-free UDP8098 discovery process on the Linux host network.
The main gateway and private workers retain their bridge network. Merely publishing
a UDP port on the bridge does not provide reliable LAN broadcast discovery.

Use only on a trusted LAN. Restrict the host firewall to the intended LAN interface
for TCP8090/UDP8098. Setup does not modify firewall rules. Wi-Fi client isolation or
separate VLANs can block discovery; both apps retain manual URL entry.

`make up` verifies/fetches the pinned core, creates missing private defaults, builds
the gateway image and starts the stack. It preserves existing credentials. Once
repository remotes are configured, the same command can restore a missing core to
`.deps`; today it uses the sibling checkout or an explicit `ZOMBIE_CORE_DIR`.
A raw standalone `docker compose up` is not yet a substitute for this preparation.
No published source URL or container registry is invented by this setup.

`ZOMBIE_BIND_IP=127.0.0.1` restricts both HTTP and the default discovery binding to
loopback. `ZOMBIE_DISCOVERY_BIND_IP` can select a separate interface deliberately;
it must describe an interface on which HTTP is actually reachable. Use the default
wildcard binding for multi-interface LAN discovery. A responding discovery process
is not continuing HTTP readiness evidence; normal pairing still checks the gateway.

No discovery container receives database mounts, provider credentials or device
secrets. It reuses the pinned gateway image in `-discovery-only` mode and depends
on initial gateway health. Optional media workers remain opt-in.
