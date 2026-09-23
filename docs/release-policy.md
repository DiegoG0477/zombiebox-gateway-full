# Frozen dependencies in every ZombieBox release

For each functional release train, review stable upstream releases, select compatible
versions and record any holdback. Freeze library locks, source commits and service
image digests before shipping. `latest` may inform a maintainer's review; no install
or runtime path follows it. A changed dependency set requires a new release.

`compose-bundle.py` requires an explicit `--version` and a new output directory. Its
`release.lock.json` records the ZombieBox version, mode, exact service identities,
packaging/configuration commits and local dirty status. Registry mode rejects mutable
images and incomplete service maps, including initializer and MediaMTX. Local mode
exports exact image IDs/layers with `pull_policy: never`. Never edit published locks.

Every end-user service is a container. The initializer image owns private bootstrap
configuration and packaged probes; no host interpreter or native toolchain is needed.
Go/Python scripts in this repository are maintainer/manual-build tools. The separate
Edge product retains its native Android/Bionic delivery.

A reference clone is neither a linked dependency nor distributed runtime. Upstream
sources stay in ignored local build checkouts or external source archives. For example,
UxPlay is packaged in the AirPlay service, while Plexgo is currently reference-only.
Libraries that are later integrated must be pinned in the relevant language lockfile.

Retain registry manifests/layers and matching notices/sources for older releases;
SHA256 identity alone does not keep a deleted artifact available. Private Docker
archives permit offline redeployment. Exact source rebuilds, public source closure,
publication and physical compatibility are separate evidence gates.

The optional dev.46 Spotify image has an unresolved dependency-license review:
the pinned `xlab/vorbis-go` module has no explicit license in its source archive
or upstream repository. The corresponding-source archive and image hash do not
grant redistribution rights. Do not treat that optional image as cleared for
further redistribution or include it in a new release until a licensed decoder
replacement is built and verified, or upstream confirms a distributable license.
This does not alter the already-published immutable image identity.
