# Filtering

Every notification passes through a chain of filters before dispatch. All filters must pass for a notification to be sent. The chain short-circuits on the first rejection.

## Filter chain

### 1. Severity

Compares the review's severity against the profile's requirement.

| Setting | Behavior |
| --- | --- |
| Alert | Only alert-severity reviews pass |
| Detection | Only detection-severity reviews pass |
| Any | Both alert and detection pass |

By default, Frigate classifies `person` and `car` objects as alerts; all other tracked objects (and audio labels) are detections. This is configurable in Frigate's [`review` config](https://docs.frigate.video/configuration/review#alerts-and-detections).

---

### 2. Object type

Checks whether the review contains any object types the profile cares about.

- If you configured specific objects (e.g., person, car), at least one must be present
- An empty object list passes all object types
- The `-verified` suffix is stripped before comparison -- `person-verified` matches a `person` filter

---

### 3. Sub-label (recognition)

Filters notifications based on Frigate's face recognition and license plate recognition sub-labels.

| Mode | Behavior |
| --- | --- |
| Disabled (default) | No sub-label filtering -- all reviews pass |
| Only recognized | Hold notifications until a `-verified` object is present. Optionally restrict to specific identities. |
| Exclude specific | Allow all notifications, but suppress once a selected identity is confirmed |

**Only recognized mode:**

- Checks review objects for the `-verified` suffix (e.g., `person-verified`) to confirm recognition has occurred
- If an include list is set, at least one sub-label must match (case-insensitive)
- If the include list is empty, any `-verified` object is sufficient
- This enables deferred-initial behavior: the `new` event may be rejected (no recognition yet), and the first `update` with a verified identity fires as the initial notification

**Exclude specific mode:**

- Passes all reviews by default
- If the review's sub-labels contain any excluded identity (case-insensitive), the notification is suppressed
- Useful for "stop alerting once you know it's a family member's car"

!!! note "Scope"

    The config flow discovers identities from Frigate's face recognition and LPR sensors. The runtime filter operates on all sub-labels regardless of source, but identities from other sources are not discoverable in the config flow UI.

!!! warning "Reload rule"

    Changes to Frigate's recognition setup (adding new faces, known plates) require a Frigate integration reload before they appear in this integration's config flow.

---

### 4. Zone

Validates the review's zones against the profile's required zones. If no required zones are configured, all zones pass.

#### Any zone (default)

At least one required zone must appear in the review.

| Required | Review | Result |
| --- | --- | --- |
| driveway, garage | driveway, yard | Pass -- driveway matches |
| driveway, garage | yard | Fail -- no overlap |

#### All zones

Every required zone must appear in the review.

| Required | Review | Result |
| --- | --- | --- |
| driveway, garage | driveway, garage, yard | Pass -- both present |
| driveway, garage | driveway | Fail -- garage missing |

#### Ordered

Zones must appear in sequence, anchored by the first required zone.

| Required | Review | Result |
| --- | --- | --- |
| A, B | A, C, B | Pass -- A first, B later |
| A, B | B, A | Fail -- B appears before A |
| A, B | A, C | Fail -- B never appears |

!!! note "Multi-camera profiles"

    Zone filtering is skipped entirely for multi-camera profiles. The zone filter fields are hidden in the config flow. A future release may support zone filtering for multi-camera profiles where all selected cameras share the same zone names.

---

### 5. Time filter

Checks the current time against a configured time window.

| Mode | Behavior |
| --- | --- |
| Notify only during this window | Notifications only fire inside the window |
| Do not notify during this window | Notifications are suppressed inside the window |

Overnight ranges are supported (e.g., 22:00--06:00 wraps around midnight).

Time filter supports [3-mode inheritance](#inheritance-pattern): Inherit shared time filter, Use profile time filter, or No time filter.

---

### 6. State filter

Checks whether an external entity is in one of the allowed states.

- If no state entity is configured, this filter is skipped
- If the entity is configured but not found in Home Assistant, its state resolves to `unavailable` and is checked against the allowed states list
- Common use cases: only notify when alarm is `armed_away`, suppress when a focus mode entity is `do_not_disturb`

Supports [3-mode inheritance](#inheritance-pattern): Inherit shared state filter, Use profile state filter, or No state filter.

---

### 7. Presence filter

Checks whether any configured `person`, `device_tracker`, or `group` entity is `home`. If any has state `home`, the notification is suppressed.

Presence is **stateless** -- it is evaluated at every lifecycle phase (initial, update, end, genai). If you arrive home mid-review, later phases for that review will be suppressed even though the initial notification was sent while you were away.

Supports [3-mode inheritance](#inheritance-pattern): Inherit shared presence filter, Use profile presence filter, or Ignore presence for this profile.

---

### 8. Silence

Checks whether the profile is currently silenced via its "Silenced Until" datetime entity. If the current time is before the silenced-until timestamp, the notification is blocked. States of `unknown` or `unavailable` are treated as not silenced. See [Notification Lifecycle -- Silence](notification-lifecycle.md#silence).

---

### 9. Switch entity

Checks the profile's enabled switch. Only an explicit `off` state blocks notifications -- any other state (including `unavailable` or `unknown`) passes. The integration looks up the switch via the entity registry using its stable unique ID, so renaming the entity in the UI has no effect.

---

### 10. Guard entity

Checks an external guard entity (`input_boolean`, `switch`, or `binary_sensor`) that gates notifications. Only an explicit `off` state blocks -- any other state passes.

Supports [3-mode inheritance](#inheritance-pattern): Inherit shared guard, Use profile guard, or No guard entity.

---

### 11. Cooldown

Only evaluated for `new` (initial) lifecycle events. If less than `cooldown_seconds` has elapsed since the last notification for this (profile, camera) pair, the new event is rejected. In-flight reviews bypass cooldown for update/end/genai events. See [Notification Lifecycle -- Cooldown](notification-lifecycle.md#cooldown).

## Inheritance pattern

Several filters support a 3-mode inheritance pattern configured per-profile:

| Mode | Behavior |
| --- | --- |
| Inherit | Use the shared value from [Global Defaults](global-defaults.md) |
| Custom / Use profile | Use a profile-specific value |
| Disabled / No filter | Skip this filter entirely |

Filters and their supported modes:

| Filter | Modes |
| --- | --- |
| Time filter | Inherit shared time filter / Use profile time filter / No time filter |
| State filter | Inherit shared state filter / Use profile state filter / No state filter |
| Guard entity | Inherit shared guard / Use profile guard / No guard entity |
| Presence | Inherit shared presence filter / Use profile presence filter / Ignore presence for this profile |

## Debugging filters

If a notification is not sending, see [Troubleshooting > Reading logs](../troubleshooting.md#reading-logs) for how to enable debug logging and interpret filter rejection messages.
