# zombiebox-gateway-full

Linux/Fedora Compose packaging and private runtime configuration.

This is an independent repository in the Zombie Box workspace. Remotes and hosted
releases are not configured yet; local commits/tags and dependency pins are real.

Depends on the exact gateway-core commit in `dependencies.lock.json`.

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
