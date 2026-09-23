# Full image publication

The installer is a versioned shell entry point. End users need Docker Engine,
Compose, `curl` and `sha256sum`; they do not build images or download Compose
files by hand. Maintainers publish **one image per process service** and record
each registry manifest digest in the release's `compose.yaml`. Gateway and
discovery share one image. A new ZombieBox release may select newer verified
upstreams, but a previously published release never follows a moving tag.

## Release gate

1. Inventory the **exact local images** to be published with
   `scripts/inventory-image.py`. For scratch images such as MediaMTX, use
   `--no-alpine --go-binary /mediamtx`. Retain image IDs and architecture.
2. Stage first-party/integrated Git archives, every linked Go module and matching
   standard-library source, npm package tarballs, exact Alpine `APKBUILD` files
   and patches with `scripts/collect-full-sources.py`. The upstream source
   checkouts must match `third_party/upstreams.lock.json`. Reference-only clones
   do not enter the distribution.
3. In a disposable Alpine maintainer container, run
   `scripts/fetch-alpine-sources.sh` against the staged recipes. It runs
   `abuild fetch verify`, leaves receipts per recipe and stops before exhausting
   host disk. If an origin URL disappears, run
   `scripts/recover-alpine-sources.py` inside the disposable container. It uses
   Alpine's versioned distfiles mirror only when the file matches the locked
   `APKBUILD` SHA512 digest; rerun the affected recipe. Do not regenerate
   checksums to make a changed source pass.
4. Run `scripts/close-full-sources.py`. It compares image inventories against all
   collected Go/npm/aports identities, checks every Alpine source SHA512 again,
   and produces bounded source assets plus `sources-index.json`. An incomplete
   image, unavailable source or missing verified receipt fails closed.
5. Push the corresponding Full source commit and annotated tag, then create a
   **public prerelease** with the source index/parts, an exact `images.tar` and
   `images.sha256`. The manual `.github/workflows/publish-ghcr.yml` verifies
   those public source assets against GitHub's SHA256 asset digests, loads the
   archive and invokes `scripts/push-ghcr.py` with the repository's scoped
   `GITHUB_TOKEN`. The script tags all nine images under this release version,
   refuses existing tags and records pushed manifest digests in a resumable
   receipt attached to the prerelease. This avoids requiring a personal
   `write:packages` token on the maintainer machine.
6. Set each new GHCR package's visibility to **public** in the organization
   package settings, then run `scripts/finalize-public-bundle.py`. It checks every
   digest with **anonymous** registry access before setting `publicationReady`.
   Upload its seven installation assets, the source index and all source parts to
   one GitHub prerelease. Verify the release asset checksums and a clean
   `docker compose pull` before adding the one-line install command to README.

Package visibility is an independent GitHub setting: pushing from a terminal
does not make a new GHCR package public. No image or release may be advertised as
public merely because `docker push` returned success.

The image set is Linux/amd64. Source closure and host startup do not assert Vizio,
iOS, Android or account compatibility; milestone exit gates remain separate.

## dev.46 publication checkpoint

The public prerelease contains all source parts, source index, exact image archive,
checksums and the receipt for nine GHCR image digests. The OCI archive stores
inventory IDs as top-level image descriptors, while `docker load` exposes config
IDs. The publisher follows and verifies the OCI descriptor-to-manifest-to-config
hash chain before it tags a loaded image. Its tested workflow completed successfully.
At this checkpoint all nine GHCR packages are private; no anonymous pull or public
Compose bundle is claimed. The generated digest-only bundle is held locally with
`publicationReady=false` until the package visibility and finalizer checks pass.
