# Filtering

How to control which Frigate reviews trigger notifications. Each example shows the minimum settings needed; see [Filtering](../reference/filtering.md) for the full filter pipeline.

## Night-only notifications

Restrict notifications to nighttime hours using the built-in time filter.

1. In your profile's **Filtering** section, expand the **Time filter**
2. Set override to "Use profile time filter"
3. Set mode to "Notify only during this window"
4. Set start time to `22:00` and end time to `06:00`

Notifications will only fire between 10 PM and 6 AM. Overnight ranges are handled automatically.

To set this as the default for all profiles, configure it in integration options under **Delivery & Filters > Time filter** instead. Profiles inherit global defaults unless overridden.

### Alternative: guard entity approach

For more complex schedules or automation-driven control:

1. Create an `input_boolean.night_mode` helper
2. Use automations to toggle it based on time, sun state, or other conditions
3. In the profile's **Filtering** section, expand **Guard entity**, set mode to "Use profile guard", and select `input_boolean.night_mode`

---

## Suppress when home (presence filter)

Only get notified when you're away from home.

1. In integration options under **Delivery & Filters**, expand the **Presence filter** section
2. Select your person entities (e.g., `person.steve`, `person.sally`)

Notifications are suppressed when any selected person is home. When everyone leaves, notifications resume.

To let a specific profile notify even when someone is home (e.g., a critical security camera), set that profile's presence mode to "Ignore presence for this profile" in the **Filtering** section.

---

## Only notify when alarm is armed (state filter)

Tie notifications to your alarm panel or any entity state.

1. In integration options under **Delivery & Filters**, expand the **State filter** section
2. Select your alarm entity (e.g., `alarm_control_panel.home`)
3. Set allowed states: `armed_away`, `armed_home`

Notifications only fire when the alarm is in one of those states.

For per-profile overrides: in the profile's **Filtering** section, set state filter to "No state filter" (always notify) or "Use profile state filter" (different entity/states).

---

## Cooldown for busy cameras

Reduce alert volume from high-traffic cameras.

1. In integration options under **Delivery & Filters > Timing**, set cooldown to 120 seconds
2. Or per-profile in **Delivery & timing** under **Rate limiting**, set cooldown override to 120

This ensures at most one new-review notification per 2 minutes per camera. Updates and end-of-review notifications for in-flight reviews still arrive normally.

---

## Only notify for a specific person (face recognition)

Get alerts only when Frigate recognizes a known face.

1. In the profile's **Filtering** section, expand the **Recognition filter**
2. Set mode to "Only recognized"
3. In "Notify only for these", select the face(s) you want alerts for (e.g., "Alice")

**How it works:** The initial notification is held until Frigate confirms a recognized face. If the first `new` event has no `-verified` object, the filter rejects it silently. When a subsequent `update` arrives with a verified identity matching your list, it fires as the initial notification. Unknown faces never trigger.

Leave the "Notify only for these" list empty to get notified for *any* recognized face.

---

## Suppress known vehicles (license plate recognition)

Stop getting alerts for your own cars.

1. In the profile's **Filtering** section, expand the **Recognition filter**
2. Set mode to "Exclude specific"
3. In "Do not notify for these", select the plate names to suppress (e.g., "Alice's Car", "Bob's Car")

**How it works:** The initial "car detected" notification fires immediately (before plate recognition runs). If Frigate later identifies the car as a known vehicle in your exclude list, update and end notifications for that review are suppressed. Unknown vehicles continue to receive all notification phases.
