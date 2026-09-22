# zombiebox-gateway-full

Linux/Fedora Compose packaging and private runtime configuration.

This is an independent repository in the Zombie Box workspace.
[Source and milestones](https://github.com/DiegoG0477/zombiebox-gateway-full) are hosted on GitHub.
Development checkpoints are not stable releases or physical compatibility claims.

Depends on the exact gateway-core commit in `dependencies.lock.json`.

## Installation

### Available now: local/source checkout

Requirements: Linux, Docker Engine with Compose v2, Python3, Git and FFmpeg with
libx264/libx265 for synthetic diagnostics. Source dependencies use the exact core
pin. In the existing workspace the sibling checkout is found automatically;
standalone cloning restores the pinned public core using `make deps`.

```sh
git clone https://github.com/DiegoG0477/zombiebox-gateway-full.git
cd zombiebox-gateway-full
make deps
bash install.sh
```

The installer prepares private configuration, builds the core image, starts core,
relay and LAN discovery, and waits for health. Credentials/SQLite/media survive
reinstallation. The Client lists discovered gateways; configure accounts/M3U in
Client Settings or the private `config/providers.json` under the printed runtime.
Use `--prepare-only` to generate/review configuration without starting services.

Default runtime: `${XDG_DATA_HOME:-$HOME/.local/share}/zombiebox/full`. To reuse the
central workspace's current runtime, run from that workspace:

```sh
ZOMBIE_RUNTIME_ROOT="$PWD" bash gateway-full/install.sh
```

Optional workers are explicit to fit small hosts:

```sh
bash install.sh --profile youtube --profile spotify
```

Supported profiles: `youtube`, `youtube-receiver`, `spotify`, `airplay`, `threadfin`,
`rebrowser`. Source builds of Spotify/AirPlay/Threadfin require their locked
references (`make -C ../gateway-core references`). Enabling a worker does not supply
accounts or certify receiver compatibility. Existing provider URLs/tokens are kept.

Only discovery and receivers that need LAN multicast use host networking. Core and
ordinary workers retain their private Compose network and resource limits. Permit
TCP8090, TCP8554 (authenticated Cast publishing) and UDP8098 on the trusted LAN in your firewall; the installer does not
change the firewall. Broadcast can be blocked by Wi-Fi isolation; manual URL works
as fallback. RTSP defaults to the LAN bind so a paired phone can publish; set
`ZOMBIE_RTSP_BIND_IP` in the private Compose env file to restrict it separately.
Relay control/HLS ports stay inside Compose and are not published to the LAN.

### Prebuilt release bundle (first publication pending)

The maintainer runs `scripts/release-bundle.py --images images.json --output DIR`
with actual reviewed `ghcr.io/...@sha256:...` references for every first-party
service. The generated bundle contains Compose, configuration helpers, relay/browser
configuration, diagnostic media and checksums. It has no source build dependency.
After downloading and verifying the published bundle, run the same `bash install.sh`.
It pulls pinned images and starts configured services; no Go, source clones or
FFmpeg encoder is required on the user's Linux host.

No public image name or download command is advertised as working before that
publication exists. Compose is the complete installation path; a bare `docker run`
command omits relay/discovery/worker configuration and is not equivalent.

```sh
make deps-check  # uses ../gateway-core or ZOMBIE_CORE_DIR
make setup      # private defaults, preserves existing credentials
make check      # all Compose profiles
make build      # gateway image
make up
make down
```

`make deps` can restore `.deps/gateway-core` after its remote is configured.
Standalone runtime defaults to this repo's `.local`; the central workspace passes
`ZOMBIE_RUNTIME_ROOT` to preserve its existing runtime. Secrets stay in private
config files, never Git. Heavy workers remain opt-in. `make sources` exports the
locked Spotify/UxPlay/Threadfin sources for their named build context. Use Compose
profiles `youtube`, `youtube-receiver`, `spotify`, `airplay`, `threadfin`, `rebrowser`
when deliberately building/starting those services. Source code belongs to core.

On the 8 GB Fedora host, keep conversion/browser concurrency bounded and probe
hardware acceleration. Container health is not proof of account readiness or A/V.

## Development rules

Run `make format` and `make format-check`. Formatters are pinned and downloaded
on first use. See [AGENTS.md](AGENTS.md), [history provenance](docs/history.md),
[component work](docs/PLANNING.md) and [local milestone registry](docs/milestones.json).
The central workspace owns product-wide ADRs, the original specification, the UI
reference, M0–M11 exit gates and the complete development/validation gap audit.
Physical devices over USB/ADB are the default; automated checks do not establish
legacy runtime or end-to-end account/media compatibility.

Dev.10 packages the core's local audio-track selection and text-subtitle endpoints.
Only the gateway image advances to `0.1.0-dev.10`; unchanged service images retain
their `dev.9` pins. These features require local media and FFmpeg. Remote tracks,
automatic language choice and bitmap burn-in remain pending.

Dev.11 advances the gateway and YouTube images for hierarchical provider browsing
and progressive remote adaptation/adaptive mux. `make remote-smoke` runs synthetic
HTTP A/V fixtures inside the packaged FFmpeg image with no external network.
`make tracks-smoke` retains the authenticated HTTP local-track regression gate.
Building an image does not replace a running container; existing services must be
recreated explicitly to consume the new image.

Dev.12 packages selected-client media reception and Cast encoder budgets in the
gateway image. YouTube remains dev.11; unchanged worker images keep their pins.
Settings → Receive Spotify / AirPlay arms the paired foreground client. It does
not provide credentials or turn process health into account/playback readiness.

Dev.13: Packages the dev.13 shared retry/live-TS core; remote smoke includes live TS conversion.

## dev.14 increment

Packages dev.14 manifest adaptation; synthetic packaged FFmpeg coverage includes HLS TS/fMP4 and DASH template/static-list A/V conversion.
The four requested block-1 changes are implemented; physical acceptance and broader product gates remain open.

Dev.16: Packages shared dev.16 gateway, YouTube, Spotify, AirPlay and browser workers. Unchanged receiver/Threadfin images retain prior pins.

## License

First-party code: [GPL-3.0-only](LICENSE). See [NOTICE](NOTICE) for third-party scope.

Dev.18 retains processed artwork across restarts in `/data/artwork` in the existing persistent state volume.
The shared cache defaults to 64 MiB/24 hours; `-artwork-cache-mb 0` disables disk
persistence. Source URLs/credentials/original images are not stored in cache files.

Dev.19: Packages dev.19 shared media, EPG, diagnostics and SQLite migration core; unchanged workers retain their existing image pins.

Dev.20: Packages shared dev.20 handoff and low-bandwidth conversion. Unchanged worker image pins are retained.

Dev.21: Packages shared dev.21 network/search/state maintenance; unchanged optional workers retain their image pins.

## dev.22 increment

Packages the shared dev.22 receiver-coordination core; optional workers retain their version pins.
No product or physical acceptance gate closes.

## dev.23 increment

LAN HTTP defaults and a constrained host-network discovery sidecar; make up prepares and builds the pinned core.
No product or physical acceptance gate closes.


## dev.24 increment

Packages the shared companion core in dev.24 and includes the QR encoder license. Existing running services are not automatically replaced.
Full visual/capture policy, extended Remote, HEVC/4K and other product gates remain open; physical acceptance stays deferred.

## dev.25 increment

One-command source/release installation, preserved private runtime, digest-only source-free bundle preparation and extended fixtures. Real hosted image digests/publication remain pending.

## dev.27 increment

Pins the shared evidence-gated 1080p Cast negotiation core. The Compose build target is dev.27; no new image was built or deployed in this checkpoint, preserving the reclaimed disk space. Active services remain unchanged. Physical and distribution gates remain open.

## dev.29 increment

Pins the shared audio-only Cast core. Source image target advances to dev.29; no image rebuild or active-service replacement is claimed.
Product milestones and physical acceptance remain open.

## dev.30 increment

Pins the shared phone-media core. Source image target advances to dev.30; active services are not replaced and no new image is claimed.
Product milestones and deferred physical gates remain open.

## dev.31 increment

Pins the shared native-inventory validation/export core. Source image target is dev.31; active dev.22 services are unchanged and no new image is claimed.
Product milestone and physical/public distribution gates remain open.

## dev.32 increment

Pins the shared legacy phone-file container increment for Full. Source image target is dev.32; active services are not replaced. Candidate build evidence is recorded in the workspace checkpoint.
Product milestones, physical validation and public distribution remain open.

## dev.34 increment

Consumes dev.34 core pairing and remote-text implementation; packaging strategy is unchanged. Public image digests, complete redistribution inventory and deployment remain separate gates.

## dev.35 increment

Packages the shared dev.35 queue/adaptation/listening core and epoch-aware YouTube receiver. Hosted source and dependency remotes are configured; public images and full binary source inventory remain separate.
