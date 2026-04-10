# Notification Profiles

**Create a profile:** Settings > Devices & Services > Notifications for Frigate > **Add notification profile**. The wizard walks through Preset and Basics, then opens a Customize menu for optional sections.

**Edit an existing profile:** Click the profile's device, then "Reconfigure" from the three-dot menu. Reconfigure shows a menu where you can jump directly to any section (including Basics). Camera selection, provider, and profile name are fixed at creation -- to change these, create a new profile.

---

## Preset

Select a starting template. [Presets](presets.md) pre-fill phase configs, templates, and defaults for common notification patterns. Every value is fully editable afterward.

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Preset** | Dropdown | Starting template: Live Alerts, Rich Alerts, End Only, Snapshot Only, Latest Only, Silent Log | Live Alerts |

If any of the profile's selected cameras has GenAI review descriptions enabled in Frigate, GenAI sections appear automatically throughout the wizard. See [Presets](presets.md#genai-auto-detection) for details.

---

## Basics

Profile identity, camera selection, provider, and notification target. This step runs in two passes: the first collects identity and provider, the second collects the target.

### Pass 1: Identity

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Profile name** | Text | Descriptive label for this profile | (required) |
| **Cameras** | Multi-select | Frigate cameras to monitor (one or more) | (required) |
| **Provider** | Dropdown | Apple (iOS Push), Android (Companion), Cross-Platform (iOS + Android group), Android TV / Fire TV | Apple (iOS Push) |

### Pass 2: Target

After selecting a provider, the step reloads to show provider-appropriate target fields:

| Field | Type | Description | Shown for |
| --- | --- | --- | --- |
| **Device** | Device picker | Mobile app device to notify | Apple, Android |
| **Notify service** | Dropdown (custom value) | Notify service or group name | All providers |
| **Tag** | Text | Notification tag template | Apple, Android, Cross-Platform |
| **Group** | Text | Notification group template | Apple, Android, Cross-Platform |

Exactly one of Device or Notify service must be filled. Tag and Group are hidden for Android TV.

> **Grouping for multi-camera profiles:** The default `{{ camera }}` in the group template resolves to the triggering camera, so each camera's notifications group independently even within a multi-camera profile.

---

## Customize menu

After Basics, the wizard presents a menu. Pick any section to configure or go straight to **Save**:

- **Filtering** -- objects, zones, guard, time, presence, state
- **Content & templates** -- message templates, subtitles, emoji, zone phrases
- **Media & actions** -- attachments, video, action buttons
- **Delivery & timing** -- sound, timing, rate limiting, platform options
- **Save profile** -- save with current settings

Every section returns to the menu after saving, so you can visit them in any order or skip entirely. On reconfigure, the menu also includes **Basics** for editing the notification target.

---

## Filtering

Controls which Frigate reviews trigger notifications. For collapsed filter sections with an inherit/custom/disabled mode, the remaining fields in that section only take effect when the mode is set to the profile-specific option.

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Object Types** | Multi-select | Object types to notify for (empty = all) | (empty) |
| **Severity** | Dropdown | Alert, Detection, or Any | Alert |
| **Required zones** | Multi-select | Zone filter (single-camera only; empty = all) | (empty) |
| **Zone match mode** | Dropdown | Any zone (at least one), All zones (every listed zone), Ordered (zones in sequence). Single-camera only. | Any zone |

**Zone match modes:**

- **Any zone** -- at least one required zone appears in the review
- **All zones** -- every required zone must appear
- **Ordered** -- zones must appear in the review in the specified sequence, anchored by the first zone

### Guard entity section (collapsed)

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Guard mode** | Dropdown | Inherit shared guard, Use profile guard, No guard entity | Inherit shared guard |
| **Guard entity** | Entity picker | Entity that gates notifications | (none) |

### Time filter section (collapsed)

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Override** | Dropdown | Inherit shared time filter, Use profile time filter, Disabled | Inherit shared time filter |
| **Mode** | Dropdown | Notify only during this window, Do not notify during this window | (none) |
| **Start time** | Time picker | Start of the window | (none) |
| **End time** | Time picker | End of the window | (none) |

### Presence filter section (collapsed)

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Presence mode** | Dropdown | Inherit shared presence filter, Use profile presence filter, Ignore presence for this profile | Inherit shared presence filter |
| **Presence entities** | Entity picker (multi) | Person, device_tracker, or group entities to check (only used when mode is "Use profile") | (none) |

### State filter section (collapsed)

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **State filter mode** | Dropdown | Inherit shared state filter, Use profile state filter, No state filter | Inherit shared state filter |
| **State entity** | Entity picker | Entity to check | (none) |
| **Required states** | Multi-select (custom values) | States that allow notifications | (none) |

### Recognition filter section (collapsed)

Shown only when any selected camera has sub-labels available (e.g., face recognition, license plate recognition). Filters based on sub-labels attached to detections.

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Recognition mode** | Dropdown | Disabled, Only recognized, Exclude specific | Disabled |
| **Notify only for these** | Multi-select | Restrict to specific identities | (empty = any recognized) |
| **Do not notify for these** | Multi-select | Block specific identities | (empty) |

> **Note:** Changes to Frigate's recognition setup (adding new faces or known plates) require a Frigate integration reload before they appear here.

See [Filtering](filtering.md) for the complete filter chain.

---

## Content & templates

Per-phase message configuration. Each enabled phase appears as a collapsed section. The GenAI section is shown only when GenAI is available for the selected cameras.

### Title template (top-level)

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Title template** | Dropdown (custom value) | Select a built-in template or type custom Jinja2. Blank = uses global default. | (blank -- uses global) |

### Per-phase sections

Each phase section contains:

| Field | Type | Description |
| --- | --- | --- |
| **Enabled** | Boolean | Whether this phase sends notifications |
| **Message template** | Dropdown (custom value) | Select a built-in template or type custom Jinja2 |
| **Subtitle template** | Dropdown (custom value) | Select a built-in template or type custom Jinja2 |
| **Emoji to message** | Boolean | Per-item emoji injection in message context |
| **Emoji to subtitle** | Boolean | Per-item emoji injection in subtitle context |

Both template fields offer built-in templates in the dropdown, or accept custom Jinja2. See [Context Variables](context-variables.md) for all available variables and [Templates](templates.md) for the built-in template list.

The two emoji toggles are only shown when global emojis are enabled in [Global Defaults](global-defaults.md#step-3-appearance). If global emojis are disabled, these toggles are hidden.

### GenAI section

The GenAI section is only shown when GenAI is available. It contains the same fields as the other phase sections (enabled, message template, subtitle template, emoji toggles) plus one extra:

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Threat level prefix in title** | Boolean | Apply the global prefix text (configured in [Global Defaults](global-defaults.md#step-3-appearance)) to the notification title based on threat level | On |

Prefix text for all three severity levels (0, 1, 2+) is configured globally. Profiles only control whether the prefix is applied.

### Zone phrase overrides section (collapsed)

Shown only for single-camera profiles where the camera has zones. One text field per zone on the selected camera. Enter an action word or phrase (e.g., "entered", "arrived at", "near") to set the `zone_phrase` template variable. Leave blank to use the default ("detected").

Zone phrases can be Jinja2 templates, rendered with the full [context variables](context-variables.md).

---

## Media & actions

Per-phase media configuration. Only phases enabled in Content & templates appear here.

Each phase section contains:

| Field | Type | Description |
| --- | --- | --- |
| **Attachment** | Dropdown | Thumbnail, Snapshot, Snapshot (bounding box), Snapshot (cropped), Snapshot (cropped + bbox), Review GIF, Event GIF |
| **Video** | Dropdown | None (use attachment), Clip (HLS), Clip (MP4), Review GIF video, Live View (iOS). Shown when provider supports video. |
| **Use latest detection** | Boolean | Use latest detection ID for media URLs (not shown for initial phase) |

Android TV profiles use a reduced attachment selector appropriate for overlay display.

### Custom actions section (collapsed)

Shown when the provider supports custom actions. One HA action selector per phase (initial, update, end, GenAI).

### Tap action section (collapsed)

Shown when the provider supports action presets.

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Tap action preset** | Dropdown | What opens when you tap the notification | View Clip |

Options: View Clip, View Snapshot, View GIF, View Live Stream, Open HA (App), Open HA (Browser), Open Frigate, No Action (Android).

### Action buttons section (collapsed)

Shown when the provider supports action presets.

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Button 1** | Dropdown | First action button preset | View Clip |
| **Button 2** | Dropdown | Second action button preset | View Snapshot |
| **Button 3** | Dropdown | Third action button preset | Silence Notifications |

Options: View Clip, View Snapshot, View GIF, View Live Stream, Silence Notifications, Open HA (App), Open HA (Browser), Open Frigate, Custom Action, No Action (Android), None (empty slot).

### Custom button action section (collapsed)

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Custom button action** | Action selector | HA action that fires when a button slot is set to "Custom Action" | (empty) |

See [Actions](actions.md) for details.

---

## Delivery & timing

Per-phase delivery settings. Only phases enabled in Content & templates appear here.

Fields vary by provider:

### Apple (iOS)

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Sound** | Text | `default`, `none`, or sound file name | `default` |
| **Volume** | Number (0-100%) | Audio volume | 100% |
| **Interruption level** | Dropdown | Active, Passive, or Time Sensitive | Active |
| **Delay** | Number (seconds) | Wait before sending | 0 |
| **Critical** | Boolean | Override DND/silent mode | Off |

### Android

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Importance** | Dropdown | Notification importance | high |
| **Priority** | Dropdown | Delivery priority | high |
| **TTL** | Number | Time to live | 0 |
| **Delay** | Number (seconds) | Wait before sending | 0 |

### Cross-Platform

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Urgency** | Dropdown | Notification urgency | (none) |
| **Delay** | Number (seconds) | Wait before sending | 0 |

### Android TV

Per-phase overlay settings:

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Font size** | Dropdown | Overlay text size | medium |
| **Position** | Dropdown | Overlay position | bottom-right |
| **Duration** | Number (seconds) | Overlay display duration | 5 |
| **Transparency** | Dropdown | Overlay transparency | 0% |
| **Interrupt** | Boolean | Interrupt current playback | Off |
| **Timeout** | Number (seconds) | Provider timeout | 30 |
| **Color** | Text | Overlay accent color (hex) | (none) |

### Rate limiting section (collapsed)

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Alert once** | Boolean | Only the first notification per review plays sound (Apple/Android only) | Off |
| **Silence duration override** | Number (minutes) | Override the shared silence duration for this profile | (none) |
| **Cooldown override** | Number (seconds) | Override the shared cooldown for this profile | (none) |

### Android delivery section (collapsed, Android / Cross-Platform only)

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Channel** | Text | Android notification channel | (none) |
| **Sticky** | Boolean | Stays until dismissed | Off |
| **Persistent** | Boolean | Cannot be swiped away | Off |
| **Android Auto** | Boolean | Show on Android Auto | Off |
| **Color** | Text | Accent color (hex) | (none) |

See [Lifecycle](notification-lifecycle.md) for how phases dispatch.

---

## Profile device

Each profile creates a **device** in Home Assistant. The device name matches the profile name. The config subentry title shows cameras for context (e.g., "Driveway / Alerts" or "Backyard, Driveway / Alerts").

| Cameras | Parent (via-device) |
| --- | --- |
| 1 camera | Frigate camera device |
| 2+ cameras | Frigate server device |

### Entities

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

### Diagnostics

Download diagnostics at Settings > Devices & Services > Notifications for Frigate > (three-dot menu) > Download diagnostics. The export includes config entry data, options, per-profile settings, and MQTT status. Profile names and notify targets are redacted for privacy.
