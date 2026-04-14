# Filter Settings

Filter settings control which Frigate reviews this profile can send. For collapsed filter sections with an inherit/custom/disabled mode, the remaining fields in that section only take effect when the mode is set to the profile-specific option.

See [Filtering](../filtering.md) for the complete filter chain.

## Objects and severity

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Object Types** | Multi-select | Object types to notify for (empty = all) | (empty) |
| **Severity** | Dropdown | Alert, Detection, or Any | Alert |

---

## Zones

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Required zones** | Multi-select | Zone filter (single-camera only; empty = all) | (empty) |
| **Zone match mode** | Dropdown | Any zone (at least one), All zones (every listed zone), Ordered (zones in sequence). Single-camera only. | Any zone |

**Zone match modes:**

- **Any zone** -- at least one required zone appears in the review
- **All zones** -- every required zone must appear
- **Ordered** -- zones must appear in the review in the specified sequence, anchored by the first zone

---

## Guard entity

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Guard mode** | Dropdown | Inherit shared guard, Use profile guard, No guard entity | Inherit shared guard |
| **Guard entity** | Entity picker | Entity that gates notifications | (none) |

---

## Time filter

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Override** | Dropdown | Inherit shared time filter, Use profile time filter, Disabled | Inherit shared time filter |
| **Mode** | Dropdown | Notify only during this window, Do not notify during this window | (none) |
| **Start time** | Time picker | Start of the window | (none) |
| **End time** | Time picker | End of the window | (none) |

---

## Presence filter

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Presence mode** | Dropdown | Inherit shared presence filter, Use profile presence filter, Ignore presence for this profile | Inherit shared presence filter |
| **Presence entities** | Entity picker (multi) | Person, device_tracker, or group entities to check (only used when mode is "Use profile") | (none) |

---

## State filter

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **State filter mode** | Dropdown | Inherit shared state filter, Use profile state filter, No state filter | Inherit shared state filter |
| **State entity** | Entity picker | Entity to check | (none) |
| **Required states** | Multi-select (custom values) | States that allow notifications | (none) |

---

## Recognition filter

!!! note "Conditional visibility"

    Shown only when any selected camera has sub-labels available (e.g., face recognition, license plate recognition). Filters based on sub-labels attached to detections.

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Recognition mode** | Dropdown | Disabled, Only recognized, Exclude specific | Disabled |
| **Notify only for these** | Multi-select | Restrict to specific identities | (empty = any recognized) |
| **Do not notify for these** | Multi-select | Block specific identities | (empty) |

!!! warning "Recognition reload"

    Changes to Frigate's recognition setup (adding new faces or known plates) require a Frigate integration reload before they appear here.
