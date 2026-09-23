# zombiebox-gateway-full: component work

## dev.64 onboarding and installable release channel

The public one-line installer follows `install-channel.txt`, which stays at
published dev.52 until a later complete Full package passes publication checks.
An explicit version still installs its frozen asset set. README separates the
public named-volume operator code from the private dev63 bundle's persistent
`full-test` code/environment and lists where each provider credential comes
from. Host installer/Compose checks do not validate physical devices or accounts.

## dev.55 onboarding documentation

Explain the actual Compose/Core/worker architecture, the published installer,
private operator code, Client-managed credentials and optional server config.
Consume Core IPTV favorites in the development pin only; published dev.52 images
and active dev.22 services remain unchanged. A rebuilt release is needed.

The product milestones relevant to this repository are M0, M6, M7, M8, M9, M11.
The local registry is a component projection of the workspace plan. Closing a
component task does not close a product-wide milestone or a physical validation gate.

Current increment: independent repository/build/dependency boundaries with filtered
history. Remaining feature development follows the ordered workspace audit:
tracks/subtitles and lifecycle; provider navigation/virtualization; measured
capabilities/native-first health; remote media adaptation; receiver finishing;
Edge operations and reproducible releases. Implement only this component's part,
and evolve shared protocol contracts in their owning repository.

Keep a separate validation track for hardware/account/latency/memory evidence.
Use development checkpoint tags until complete exit gates are evidenced. Hosted
issues/milestones can be attached to the shared GitHub Project once remotes exist.

## dev.11 increment

Gateway and YouTube dev.11 image pins, shared remote/browse implementation and synthetic packaged FFmpeg smoke. Running services are not automatically replaced.
No product milestone or physical/account gate is completed by this checkpoint.

## dev.12 increment

Packages shared reception and Cast budgets. Gateway image dev.12, YouTube dev.11, other worker pins unchanged.

## dev.13 increment

Packages the dev.13 shared retry/live-TS core; remote smoke includes live TS conversion.
No product milestone or physical/account gate closes with this checkpoint.

## dev.14 increment

Packages dev.14 manifest adaptation; synthetic packaged FFmpeg coverage includes HLS TS/fMP4 and DASH template/static-list A/V conversion.
The four requested block-1 changes are implemented; physical acceptance and broader product gates remain open.

## dev.16 increment

Packages shared dev.16 gateway, YouTube, Spotify, AirPlay and browser workers. Unchanged receiver/Threadfin images retain prior pins.
Product exit gates and physical/account acceptance remain open.

## dev.17 increment

Packages dev.17 images with first-party GPL notices. Core behavior remains shared with Edge.

No product milestone or physical gate is closed.

## dev.18 increment

Dev.18: bounded persistent artwork derivatives, restart reuse, private cache keys, device/layout profiles and conditional HTTP caching. No physical milestone closes.

## dev.21 increment

Packages shared dev.21 network/search/state maintenance; unchanged optional workers retain their image pins.
No physical, account or product milestone closes.

Verification: Compose configuration, image build, isolated startup/pairing/restart persistence, packaged track/subtitle conversion and remote-media checks pass on Fedora. This does not validate account or physical A/V behavior.

## dev.22 increment

Packages the shared dev.22 receiver-coordination core; optional workers retain their version pins.
No product or physical acceptance gate closes.

Verification: Compose configuration, Full image build, packaged track/remote-media checks and isolated startup/pairing/restart smoke pass on Fedora.

## dev.23 increment

Trusted-LAN HTTP default and constrained host-network discovery sidecar; make up prepares/builds exact core.
Product exit gates and deferred physical acceptance remain open.


## dev.24 increment

Packages the shared companion core in dev.24 and includes the QR encoder license. Existing running services are not automatically replaced.
Full visual/capture policy, extended Remote, HEVC/4K and other product gates remain open; physical acceptance stays deferred.

Verification: All Compose profiles validate and the dev.24 image builds with the QR encoder license. The existing dev.22 service remains healthy and unchanged.

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

## dev.34 implementation checkpoint

Consumes dev.34 core pairing and remote-text implementation; packaging strategy is unchanged. Public image digests, complete redistribution inventory and deployment remain separate gates.
Product exit gates and deferred physical acceptance remain open.

## dev.35 checkpoint

Packages the shared dev.35 queue/adaptation/listening core and epoch-aware YouTube receiver. Hosted source and dependency remotes are configured; public images and full binary source inventory remain separate.
Product milestone completion still requires its recorded acceptance gates.


## dev.37 implementation checkpoint

Runtime image source inventory and DIAL notices; bounded temporary space for external ASS conversion. Complete corresponding-source/image distribution remains open.

## dev.40 reception and diagnostics increment

Consumes the same endpoint-diagnostic core. No image deployment or new runtime validation; complete source/notices and immutable image delivery remain open. Product milestones remain open.

## dev.41 guide and audio selection increment

Pins the shared capability-aware audio-selection core. No image build, active deployment or new binary publication in this checkpoint. Product and physical gates remain open.

## dev.42 navigation and preferred-audio increment

Dev.42: pin the shared preferred-audio planner. No new binary image or worker distribution; complete Full image/source delivery remains open.

## dev.43 navigation and functional media increment

Dev.43: gateway image includes the shared software pipeline diagnostic. Immutable image inventory reads copied Go binary hashes, linked modules and build identities without execution. Complete OS/worker corresponding sources and GHCR bundle delivery remain open.

## dev.44 — frozen Full evaluation bundle

Author priority: prepare Full for the first physical evaluation before completing
public corresponding-source distribution and optional Edge modules. Tools remain
independent Docker services; upstream clones are ignored build inputs. Private
offline bundles preserve exact local image IDs, all service layers, platform,
configuration helpers and checksums, with no registry pulls or source builds at
install time. Public GHCR manifest digests and source compliance remain separate.
The device test manual lives outside all repositories. Physical execution has not
yet taken place; no milestone closes.

## dev.45 — Docker-only installation and per-release dependency sets

Full end users require only Docker Engine and Compose. Initialization runs in its
own container with no network, preserves private configuration in named volumes
and provides packaged probes before gateway/workers start. New bundles require an
explicit ZombieBox version and freeze all service identities, including initializer
and MediaMTX. Functional releases review current stable upstream versions and pin
the compatible set; old release locks/images are retained. Go/Python source/build
tools remain maintainer-only. Public GHCR/source closure and physical gates stay open.

## dev.47 — corresponding sources and GHCR image publication

The dev.46 prerelease now carries complete corresponding sources, the exact nine-image
Docker archive and a GHCR digest receipt. The publisher validates OCI image digests
against loaded config IDs before tagging. All images were pushed under distinct
versioned service names; at this checkpoint GHCR packages are private, so anonymous
pull, the public Compose assets and the one-line README command remain gated.
This checkout consumes the test-only Core dev.44 media coverage increment; the
dev.46 image and source identities stay frozen. Active dev.22 services were not
replaced. No product or physical milestone closes.

## dev.48 — public Full installation

The source-complete dev.46 image set now has nine publicly pullable GHCR digests.
Seven checksummed Compose installation assets are attached to the same prerelease.
Their remote digests match local files, and a clean anonymous Docker config pulled
all nine images. The version-pinned installer fetched and verified the release and
its pull/up sequence passed with Docker simulated; active dev.22 services were not
replaced. The root and Full READMEs now make that one-line command the default.
Product milestones, physical devices and real provider accounts remain unverified.

## dev.49 — shared Core pin alignment

Full's development checkout consumes Core dev.45, matching the Edge and workspace
pins. This only admits the Node24-compatible wrapper contract for future builds.
The published dev.46 images, source archives, manifest digests and one-line
installer remain immutable at their original Core commit. No image was rebuilt or
running service replaced. Product and physical gates remain open.

## dev.51 — dependency-license gate on optional Spotify

Full now consumes Core dev.46's authenticated DASH alternate-audio host coverage.
The published dev.46 images and source identities remain frozen. A later source
review found no explicit license for `xlab/vorbis-go`, a binding linked by the
optional Spotify image. The dev.46 release notes and current installation docs
flag that image for review; default Compose does not start Spotify. Replace the
binding with a reviewed distributable decoder or obtain an explicit upstream
license before a new Spotify image is shipped. All product/physical gates remain
open and active dev.22 services are unchanged.

## dev.52 — licensed Spotify source-revision packaging

Full consumes Core dev.47 and stages the reviewed MIT Ogg/Vorbis Spotify patch
from an exact clean upstream checkout. A source-revision packager validates the
new image inventory against the public dev.46 source base: unchanged services
retain their immutable image/source identities, while Spotify receives a new
image inventory, patched source, Core and Full source snapshots, and every linked
Go module archive. The old dev.46 release remains frozen and its Spotify license
gate remains disclosed. The new public release, anonymous pull and device/account
behavior require separate evidence. Active dev.22 services are unchanged.

## dev.53 — public licensed Full image set

A new dev.52 prerelease now supplies nine digest-pinned public GHCR images, eight
unchanged from dev.46 and one licensed Spotify replacement. Its SHA256-pinned
source index links the three immutable dev.46 source parts and the new 16 MB
Spotify source revision. GitHub asset hashes, anonymous registry manifest access,
checksummed installer download and simulated pull/up passed. The versioned
installer and main README now select dev.52. The active dev.22 containers were
not changed. Runtime, account and physical-device gates remain open.

## dev.54 — shared AirPlay receiver coverage pin

The development checkout consumes Core dev.48's authenticated video-to-audio-to-idle
receiver integration test. Public Full dev.52 digests and source identities remain
frozen; no image was rebuilt or active dev.22 service replaced. Host checks pass.
Real iOS, provider-account and device playback remain unverified.

## v0.1.0-dev.56 — shared IPTV category pin

Dev.56: Pins Core dev.50 IPTV category contract and host tests. Published Full dev.52 images/source identities and active dev.22 remain unchanged; runtime and product acceptance are open.

## v0.1.0-dev.57 — account/receiver pin

Dev.57: Pins Core dev.51 YouTube account OAuth and Spotify receiver lifecycle host coverage; adds optional OAuth environment to source Compose and README. Published Full dev.52 images remain frozen; real accounts and devices are unverified.

## v0.1.0-dev.63 — licensed Spotify image in source/private Full

The source Compose graph now selects the reviewed Spotify dev.52 image by its
published digest, not the earlier local image with the unresolved decoder
license. Private offline bundles include that frozen image. Source installation
no longer builds Spotify from local clones; AirPlay and Threadfin remain opt-in
source builds. This aligns private first-test packaging with the reviewed public
source set; real Spotify account and receiver behavior remain acceptance gates.

## v0.1.0-dev.62 — current gateway source closure

A source-revision builder can stage the current gateway image's corresponding
Core/Full sources while inheriting unchanged reviewed Full service sources from
the public dev.46/dev.52 chain. It checks the exact local image, linked Go
module ZIP/mod hashes, Go standard-library source and Alpine recipe commits.
This prepares a reviewable source delta; GitHub/GHCR upload and physical
acceptance remain separate.

## v0.1.0-dev.61 — bounded probe reuse in private packaging

The private offline bundle builder can reuse its locally cached UHD diagnostic
samples. Core validates codec, profile, level, SDR metadata, size and duration
before accepting them, and regenerates invalid samples. This avoids repeated 4K
encoding on the constrained development host while preserving artifact hashes
and the separate physical decoder gate.

## v0.1.0-dev.60 — persistent private operator code

Source and offline Full setup now creates one private six-digit operator code,
preserves it across reruns and rejects a conflicting Compose environment. The
README distinguishes public initializer credentials from the private bundle's
`full-test` runtime and optional worker profiles. No public release or physical
gateway/TV acceptance follows from the host tests.

## v0.1.0-dev.59 — account recovery core pin

Dev.59 pins Core dev.53 and assigns a new local gateway/discovery image identity
for bounded early YouTube access-token rejection recovery. This source checkout
does not change public dev.52 image digests or the active dev.22 services. Real
account consent, quota and TV playback remain later acceptance gates.

## v0.1.0-dev.58 — golden media core pin

Dev.58: Pins Core dev.52 golden media fixtures and gives the source-built gateway/discovery image a new dev.58 local tag. Public Full dev.52 digests and active dev.22 remain unchanged; RTSP/account/device acceptance remains open.

The local dev.58 gateway image was built from this clean Core pin. Isolated
packaged track/subtitle/SQLite and remote HLS/DASH/live A/V smokes pass; they
started only temporary test containers. No active service was upgraded and no
registry or release asset was published.
