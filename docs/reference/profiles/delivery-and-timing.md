# Delivery & Timing

Delivery and timing control how each phase arrives. Per-phase delivery settings -- only phases enabled in Content & Templates appear here.

Fields vary by provider:

## Apple (iOS)

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Sound** | Text | `default`, `none`, or sound file name | `default` |
| **Volume** | Number (0-100%) | Audio volume | 100% |
| **Interruption level** | Dropdown | Active, Passive, or Time Sensitive | Active |
| **Delay** | Number (seconds) | Wait before sending | 0 |
| **Critical** | Boolean | Override DND/silent mode | Off |

---

## Android

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Importance** | Dropdown | Notification importance | high |
| **Priority** | Dropdown | Delivery priority | high |
| **TTL** | Number | Time to live | 0 |
| **Delay** | Number (seconds) | Wait before sending | 0 |

---

## Cross-Platform

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Urgency** | Dropdown | Notification urgency | (none) |
| **Delay** | Number (seconds) | Wait before sending | 0 |

---

## Android TV

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

---

## Rate limiting

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Alert once** | Boolean | Only the first notification per review plays sound (Apple/Android only) | Off |
| **Silence duration override** | Number (minutes) | Override the shared silence duration for this profile | (none) |
| **Cooldown override** | Number (seconds) | Override the shared cooldown for this profile | (none) |

---

## Android delivery

!!! note "Conditional visibility"

    Shown for Android and Cross-Platform providers only.

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| **Channel** | Text | Android notification channel | (none) |
| **Sticky** | Boolean | Stays until dismissed | Off |
| **Persistent** | Boolean | Cannot be swiped away | Off |
| **Android Auto** | Boolean | Show on Android Auto | Off |
| **Color** | Text | Accent color (hex) | (none) |

See [Lifecycle](../notification-lifecycle.md) for how phases dispatch.
