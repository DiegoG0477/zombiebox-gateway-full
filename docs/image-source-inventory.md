# Immutable image source inventory

Run the inventory before preparing a binary distribution:

```sh
python3 scripts/inventory-image.py --image sha256:EXACT_LOCAL_IMAGE_ID --output /new/path/inventory.json
```

The tool creates a stopped, network-disabled container, copies Alpine's installed
package database and the optional npm runtime lock, then removes that temporary
container. It never runs the image or reads runtime/provider configuration.

Every installed OS package records its version, license expression, source origin
and exact aports recipe commit. Source origins are deduplicated. Package file
metadata cannot overwrite package headers. Unknown recipe commits fail closed.
The npm inventory records resolved versions and integrity where present.

This is a source collection input, not a complete SBOM or release authorization.
Every `requiredSources` entry starts uncollected. Manually copied Go binaries,
Chromium/worker additions and corresponding source archives must also be accounted
for before publishing images. Missing npm locks are reported rather than interpreted
as evidence that the image has no JavaScript dependencies. Non-Alpine images need
their own inventory adapter.

The inspected dev.35 gateway image contained 120 OS packages from 102 source recipe
revisions. No Full binary publication is claimed by that inventory. Dev.37 adds the
DIAL protocol notice to first-party runtime images and a bounded 16-MiB `/tmp` to
the read-only gateway for private subtitle conversion files; private media/state
remain in their existing mounts.

## Copied Go binaries (dev.43)

Add `--go-binary /zombied` or repeat it for explicit `/usr/local/bin/...` programs.
The tool copies only the selected immutable image's executable into a private
workspace and uses `go version -m` to read it. The image/program is never executed.
Inventory records binary SHA256/size, Go toolchain, main package/module, linked
dependency versions/checksums and allowlisted build settings. Module replacements
fail for explicit review; local build flags and arbitrary paths are not exported.

For example, Spotify needs both `/usr/local/bin/go-librespot` and
`/usr/local/bin/zombie-worker`. AirPlay also has the worker, but UxPlay and native
libraries still require their separate source inventory. Node runtime and manually
copied non-Go programs are not silently marked covered. All sourceCollected flags
remain false until corresponding archives have actually been collected and reviewed.

A stopped-container inspection of all seven existing dev.37 first-party runtime
images found 237 distinct OS source recipe revisions, 146 npm entries across images
and five Go executables. This is a concrete source-collection input, not complete
source delivery or a claim those older images contain the current source checkpoint.
