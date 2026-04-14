# Global Defaults

Global defaults apply across all [profiles](profiles/index.md). Configure via Settings > Devices & Services > Notifications for Frigate > **Configure**.

The options flow has three sections. On first configure they run in sequence; on reconfigure a menu lets you jump directly to any section. Profiles inherit these values unless they override them.

---

## Delivery & Filters

Core delivery settings and shared gating filters.

| Field | Type | Description | Default |
| ------- | ------ | ------------- | --------- |
| **Home Assistant URL** | Dropdown (custom) | Base URL for attachment links. Auto-detects external/internal URLs. | External URL |
| **Frigate URL** | Dropdown (custom) | URL for the "Open Frigate" action. Auto-detects addon ingress. | (auto-detected) |

!!! tip "URL selection"

    The base URL constructs snapshot, GIF, and clip URLs in notifications. The external URL is usually best for off-network delivery. The Frigate URL powers the "Open Frigate" action button -- addon users get auto-detected ingress, external Frigate users enter a full URL (e.g. `https://frigate.local:5000`).

### Timing section (collapsed)

| Field | Type | Description | Default |
| ------- | ------ | ------------- | --------- |
| **Initial delay** | Number (0--10s, 0.5s steps) | Wait before sending the first notification. Allows Frigate time to produce a better snapshot and detect zones. | `1.0` |
| **Silence duration** | Number (1--480 min) | How long the "Silence" action button mutes a profile. | `30` |
| **Cooldown** | Number (0--3600s) | Min seconds between new notifications per camera. 0 = disabled. | `0` |

### Guard entity section (collapsed)

| Field | Type | Description | Default |
| ------- | ------ | ------------- | --------- |
| **Guard entity** | Entity picker | Toggle that gates all profiles using "Inherit shared guard" mode. | (none) |

Supported entity types: `input_boolean`, `switch`, `binary_sensor`. When the guard entity is off, all inheriting profiles suppress notifications.

### Time filter section (collapsed)

| Field | Type | Description | Default |
| ------- | ------ | ------------- | --------- |
| **Mode** | Dropdown | Notify only during this window, Do not notify during this window. Leave blank to disable. | (disabled) |
| **Start time** | Time picker | Start of the filter window. Overnight ranges supported (e.g. 22:00--06:00). | (none) |
| **End time** | Time picker | End of the filter window. | (none) |

### Presence filter section (collapsed)

| Field | Type | Description | Default |
| ------- | ------ | ------------- | --------- |
| **Presence entities** | Entity picker (multi) | `person`, `device_tracker`, or `group` entities. Suppresses notifications when any is home. | (none) |

### State filter section (collapsed)

| Field | Type | Description | Default |
| ------- | ------ | ------------- | --------- |
| **Entity** | Entity picker | Only notify when this entity is in one of the allowed states. | (none) |
| **Required states** | Multi-select (custom values) | States that allow notifications through. | (none) |

---

## Appearance & Formatting

Title template, emoji configuration, and GenAI title prefixes.

### Title template

| Field | Type | Description | Default |
| ------- | ------ | ------------- | --------- |
| **Title template** | Dropdown (custom) | Select a built-in template or type custom Jinja2 for the notification title. | `camera_time` ("Driveway - 3:45 PM") |

This is the shared default. Individual profiles can override it in their Content & templates section (leave the profile field blank to keep using this global value).

See [Context Variables](context-variables.md) for available variables and [Templates](templates.md#title-templates) for the built-in title list.

### Emoji section

| Field | Type | Description | Default |
| ------- | ------ | ------------- | --------- |
| **Enable emojis** | Boolean | When OFF, all emoji output is suppressed globally -- object emojis, phase emojis, `{{ emoji }}` template variable all resolve to empty strings. | On |
| **Default emoji** | Text | Fallback emoji when the detected object has no mapping. | 🔔 |

### Custom emoji mappings section (collapsed)

| Field | Type | Description | Default |
| ------- | ------ | ------------- | --------- |
| **Object-to-emoji map** | Object (YAML) | Custom emoji mappings. Pre-filled with built-in defaults. | (built-in defaults) |

Custom mappings are applied on top of the built-in defaults when emojis are enabled. When emojis are disabled, mappings are preserved but have no effect.

### Phase emoji overrides section (collapsed)

| Field | Type | Description | Default |
| ------- | ------ | ------------- | --------- |
| **Initial** | Text | Emoji for the initial phase. | 🆕 |
| **Update** | Text | Emoji for the update phase. | 🔄 |
| **End** | Text | Emoji for the end phase. | 🔚 |
| **GenAI** | Text | Emoji for the GenAI phase. | ✨ |

### GenAI title prefix defaults section (collapsed)

Only shown when GenAI capability is detected from the linked Frigate config.

| Field | Type | Description | Default |
| ------- | ------ | ------------- | --------- |
| **Routine (level 0)** | Text | Prefix for benign AI events. | (empty) |
| **Notable (level 1)** | Text | Prefix for notable AI events. | ⚡ |
| **Concerning (level 2)** | Text | Prefix for concerning AI events. | ⚠️ |

Profiles control whether the prefix is applied via the "Threat level prefix in title" toggle in their Content & templates section. The text itself is only configured here.

### Face emoji overrides section (collapsed)

Only shown when trained faces are stored in the Frigate integration's entity registry. One text field per discovered face.

| Field | Type | Description | Default |
| ------- | ------ | ------------- | --------- |
| *{face_name}* | Text | Emoji override for this face (e.g., `👧`). | (empty) |

### License plate emoji overrides section (collapsed)

Only shown when known plates are stored in the Frigate integration's entity registry. One text field per discovered plate name.

| Field | Type | Description | Default |
| ------- | ------ | ------------- | --------- |
| *{plate_name}* | Text | Emoji override for this plate (e.g., `🚙`). | (empty) |

Sub-label emoji overrides map recognized identities to emojis. The fallback chain is: sub-label override → emoji map → default emoji. Empty fields are ignored.

!!! warning "Reload rule"

    Changes to Frigate's recognition setup (adding new faces or known plates) require a Frigate integration reload before they appear here.

---

## Zone Aliases

One collapsed section per camera with zones. Cameras without zones are not shown.

Each zone gets a text field for its friendly alias. The alias becomes the `{{ zone_alias }}` [context variable](context-variables.md) in notifications.

| Field | Type | Description | Default |
| ------- | ------ | ------------- | --------- |
| *{zone_name}* | Text | Friendly display name for this zone. | Humanized zone name (snake_case to Title Case) |

**Example:** Rename `front_yard` to "the Front Yard" so notifications read "Person crossed the Front Yard" instead of "Person crossed Front Yard".

Zone aliases also work inside [template expressions](context-variables.md) like `{{ object }} {{ zone_phrase }} {{ zone_alias }}`.

---

## Inheritance model

Profiles inherit global defaults unless they override them. Each inheritable filter uses a 3-mode pattern:

| Mode | Behavior |
| ------ | ---------- |
| **Inherit** | Use the global default from this page |
| **Custom** | Use a profile-specific value |
| **Disabled** | Explicitly turn the feature off |

This pattern applies to: time filter, guard entity, presence filter, and state filter. Cooldown uses a different model -- profiles set a numeric override (or leave blank to inherit).

**Example:** A global time filter set to "Notify only during 22:00--06:00" applies to every profile that uses inherit mode. A profile can override this with its own window (custom) or bypass the filter entirely (disabled).

See [Profiles](profiles/index.md) for how individual profiles configure overrides.
