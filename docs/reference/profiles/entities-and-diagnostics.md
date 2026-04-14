# Entities & Diagnostics

Entities and diagnostics describe what Home Assistant exposes for each profile and for the integration itself.

## Profile device

Each profile creates a **device** in Home Assistant. The device name matches the profile name. The config subentry title shows cameras for context (e.g., "Driveway / Alerts" or "Backyard, Driveway / Alerts").

| Cameras | Parent (via-device) |
| --- | --- |
| 1 camera | Frigate camera device |
| 2+ cameras | Frigate server device |

### Profile entities

| Entity | Type | Category | Default | Persistent | Description |
| --- | --- | --- | --- | --- | --- |
| Enabled | Switch | Config | On | Yes | Toggle notification dispatch for this profile |
| Last sent | Sensor | Diagnostic | Disabled | Yes | State = review ID; attributes: review_id, phase, title, message |
| Silenced until | Datetime | Config | -- | Yes | Silence expiry timestamp, set via action tap or dashboard |
| Silenced | Binary sensor | -- | Off | -- | Whether the profile is currently silenced (derived from datetime) |
| Dispatch problem | Binary sensor | Diagnostic | Off | -- | On when a dispatch failure occurs; `last_error` attribute |
| Silence | Button | Config | -- | -- | Sets silenced-until to now + duration |
| Clear silence | Button | Config | -- | -- | Clears the silenced-until timestamp |

Deleting the device also deletes the profile subentry.

---

## Integration device

The integration also creates a shared integration-level device for entry-wide diagnostics.

### Integration entities

| Entity | Type | Category | Default | Persistent | Description |
| --- | --- | --- | --- | --- | --- |
| MQTT connected | Binary sensor | Diagnostic | Off | No | Whether Home Assistant's MQTT client is currently connected |
| Notifications sent | Sensor | -- | On | Yes | Running total of notifications sent, with per-camera and per-profile counters |
| Reset stats | Button | Config | -- | -- | Resets the notifications-sent counter |
| Review debug | Sensor | Diagnostic | Disabled | No | Latest raw review summary seen by the integration for debugging |
| Camera `<name>` | Binary sensor | Diagnostic | Disabled | No | `On` when the camera still exists in Frigate config; attributes include discovered capabilities such as `genai` |

---

## Diagnostics export

Download diagnostics at Settings > Devices & Services > Notifications for Frigate > (three-dot menu) > Download diagnostics. The export includes config entry data, options, per-profile settings, and MQTT status. Profile names and notify targets are redacted for privacy.
