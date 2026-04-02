#!/usr/bin/with-contenv bash
# Preconfigure the Home Assistant container on first boot.
#
# Adapted from:
# https://github.com/blakeblackshear/frigate-hass-integration/blob/master/.devcontainer/scripts/homeassistant_preconfig.sh
#
# Seeds auth, onboarding, and dev user password so HA skips the setup wizard.
#
# Set HA_PRECONFIG=false to skip and start with a fresh HA instance.
# Set FN_PRECONFIG=false to skip frigate_notifications config entry (add via UI).
# To re-run: remove the HA container and create a new one.

set -euo pipefail

readonly markfile="/config/.preconfigured"
readonly preconfig="${HA_PRECONFIG:-true}"
readonly fn_preconfig="${FN_PRECONFIG:-true}"

if [[ "${preconfig}" == "true" ]]; then
    if [[ -f "${markfile}" ]]; then
        echo "Preconfigured already" >&2
    else
        echo "Preconfiguring Home Assistant for FN development..." >&2

        mkdir -p /config/.storage
        cp --force --verbose /preconfig.d/.storage/* /config/.storage/

        if [[ "${fn_preconfig}" != "true" ]]; then
            echo "FN_PRECONFIG=${fn_preconfig} — stripping frigate_notifications config entry" >&2
            jq '.data.entries |= [.[] | select(.domain != "frigate_notifications")]' \
                /config/.storage/core.config_entries > /tmp/config_entries.tmp &&
            mv /tmp/config_entries.tmp /config/.storage/core.config_entries
        fi

        echo "Setting password for user 'dev'" >&2
        hass --script auth --config /config change_password dev dev

        # HA's requirement manager doesn't reliably install custom integration
        # deps on first boot with pre-seeded config entries (known HA issue).
        # Install them explicitly so integrations load on first start.
        jq -r '.requirements[]?' /config/custom_components/*/manifest.json 2>/dev/null \
            | xargs -r python3 -m uv pip install --quiet || true

        touch "${markfile}"
        echo "Preconfigured successfully" >&2
    fi
else
    echo "HA_PRECONFIG=${preconfig} — skipping storage preconfiguration (fresh mode)" >&2
fi
