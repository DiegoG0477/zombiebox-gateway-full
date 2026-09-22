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
