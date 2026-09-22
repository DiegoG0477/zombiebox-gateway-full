#!/bin/sh
# Run inside a maintainer Alpine container with staged exact APKBUILDs mounted.
set -eu

STAGING=${STAGING:-/staging}
DISTFILES=${DISTFILES:-/distfiles}
mkdir -p "$DISTFILES/verified" "$DISTFILES/logs"

failed=0
for recipe in "$STAGING"/*/APKBUILD; do
    [ -f "$recipe" ] || continue
    directory=${recipe%/APKBUILD}
    name=${directory##*/}
    [ -f "$DISTFILES/verified/$name" ] && continue
    free_kib=$(df -Pk "$DISTFILES" | awk 'NR == 2 {print $4}')
    if [ "$free_kib" -lt 3145728 ]; then
        printf 'Only %s KiB free; stopping before %s\n' "$free_kib" "$name" >&2
        exit 2
    fi
    rm -rf /tmp/zombie-aport
    cp -a "$directory" /tmp/zombie-aport
    if abuild -F -C /tmp/zombie-aport -s "$DISTFILES" fetch verify \
        >"$DISTFILES/logs/$name.log" 2>&1; then
        : >"$DISTFILES/verified/$name"
        printf 'verified %s\n' "$name"
    else
        printf 'FAILED %s (see logs)\n' "$name" >&2
        failed=$((failed + 1))
    fi
done
rm -rf /tmp/zombie-aport
[ "$failed" -eq 0 ] || exit 1
