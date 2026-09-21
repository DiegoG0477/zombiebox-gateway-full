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
