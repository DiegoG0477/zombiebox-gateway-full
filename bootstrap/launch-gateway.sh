#!/bin/sh
set -eu
IFS= read -r ZOMBIE_RELAY_ADMIN_TOKEN </config/relay.key
IFS= read -r ZOMBIE_PAIRING_CODE </config/operator.code
case "$ZOMBIE_RELAY_ADMIN_TOKEN" in
    '' | *[!0-9a-f]*)
        echo 'Invalid relay key' >&2
        exit 1
        ;;
esac
case "$ZOMBIE_PAIRING_CODE" in
    '' | *[!0-9]*)
        echo 'Invalid operator code' >&2
        exit 1
        ;;
esac
export ZOMBIE_RELAY_ADMIN_TOKEN ZOMBIE_PAIRING_CODE
exec /zombied "$@"
