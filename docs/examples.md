# Examples

Practical examples for common notification setups.

---

## Filtering

### Night-only notifications

Use the built-in time filter to restrict notifications to nighttime hours:

1. In your profile's **Filtering** section, expand the **Time filter**
2. Set override to "Use profile time filter"
3. Set mode to "Notify only during this window"
4. Set start time to `22:00` and end time to `06:00`

Notifications will only fire between 10 PM and 6 AM. Overnight ranges are handled automatically.

To set this as the default for all profiles, configure it in integration options under **Delivery & Filters > Time filter** instead. Profiles inherit global defaults unless overridden.

#### Alternative: guard entity approach

For more complex schedules or automation-driven control:

1. Create an `input_boolean.night_mode` helper
2. Use automations to toggle it based on time, sun state, or other conditions
3. In the profile's **Filtering** section, expand **Guard entity**, set mode to "Use profile guard", and select `input_boolean.night_mode`

### Suppress when home (presence filter)

Only get notified when you're away from home:

1. In integration options under **Delivery & Filters**, expand the **Presence filter** section
2. Select your person entities (e.g., `person.steve`, `person.sally`)

Notifications are suppressed when any selected person is home. When everyone leaves, notifications resume.

To let a specific profile notify even when someone is home (e.g., a critical security camera), set that profile's presence mode to "Ignore presence for this profile" in the **Filtering** section.

### Only notify when alarm is armed (state filter)

Tie notifications to your alarm panel or any entity state:

1. In integration options under **Delivery & Filters**, expand the **State filter** section
2. Select your alarm entity (e.g., `alarm_control_panel.home`)
3. Set allowed states: `armed_away`, `armed_home`

Notifications only fire when the alarm is in one of those states.

For per-profile overrides: in the profile's **Filtering** section, set state filter to "No state filter" (always notify) or "Use profile state filter" (different entity/states).

### Cooldown for busy cameras

If a camera generates too many alerts (e.g., a driveway with constant traffic):

1. In integration options under **Delivery & Filters > Timing**, set cooldown to 120 seconds
2. Or per-profile in **Delivery & timing** under **Rate limiting**, set cooldown override to 120

This ensures at most one new-review notification per 2 minutes per camera. Updates and end-of-review notifications for in-flight reviews still arrive normally.

### Only notify for a specific person (face recognition)

If your Frigate instance has face recognition enabled and known faces configured:

1. In the profile's **Filtering** section, expand the **Recognition filter**
2. Set mode to "Only recognized"
3. In "Notify only for these", select the face(s) you want alerts for (e.g., "Alice")

**How it works:** The initial notification is held until Frigate confirms a recognized face. If the first `new` event has no `-verified` object, the filter rejects it silently. When a subsequent `update` arrives with a verified identity matching your list, it fires as the initial notification. Unknown faces never trigger.

Leave the "Notify only for these" list empty to get notified for *any* recognized face.

### Suppress known vehicles (license plate recognition)

If your Frigate instance has LPR enabled with known plates:

1. In the profile's **Filtering** section, expand the **Recognition filter**
2. Set mode to "Exclude specific"
3. In "Do not notify for these", select the plate names to suppress (e.g., "Alice's Car", "Bob's Car")

**How it works:** The initial "car detected" notification fires immediately (before plate recognition runs). If Frigate later identifies the car as a known vehicle in your exclude list, update and end notifications for that review are suppressed. Unknown vehicles continue to receive all notification phases.

---

## Templates & content

### Basic person alert

A simple profile that notifies whenever a person is detected on the front door camera.

**Basics:**

- Camera: `front_door`
- Objects: `person`
- Severity: `alert`

**Content & templates:**

- Message template: `{{ object }} {{ zone_phrase }} {{ zone_alias }}`
- Emoji in message: on

**Result:**

- No zones configured: "👤 Person detected"
- With zones (e.g. `front_yard`): "👤 Person detected Front Yard" (auto-generated alias)
- With zone phrase override + alias: "👤 Person arrived at the Front Door"

### Zone-aware messages

Set up zone phrase overrides to describe what's happening:

1. In the profile's **Content & templates** section, set zone phrase overrides:
   - `front_yard`: "entered"
   - `garage`: "near"
   - `porch`: "at"

2. In integration options, set zone aliases:
   - `front_yard`: "the Driveway"
   - `garage`: "the Garage"
   - `porch`: "the Front Door"

3. With the message template `{{ object }} {{ zone_phrase }} {{ zone_alias }}` and emoji in message enabled:
   - "👤 Person entered the Driveway"
   - "🚘 Car near the Garage"
   - "👤 Person at the Front Door"

### Rich alerts with phase emoji

Use the **Rich Alerts** preset for detailed multi-phase notifications.

**Key template variables:**

- `{{ phase_emoji }}` -- phase indicator (🆕 🔄 🔚 ✨)
- `{{ subject }}` / `{{ subjects }}` -- detected object(s) with sub-labels applied
- `{{ added_subject }}` -- newly detected object in update messages

**Example title template:** `{{ phase_emoji }} {{ camera_name }}`

**Example update message:** `{{ added_subject }} also detected` -- shows what changed since the initial notification.

**Example flow:**

- 🆕 Person entered the Driveway
- 🔄 Person entered the Driveway / Car detected
- 🔚 Pending AI Summary
- ✨ A person walked down the driveway and got into a parked car.

### AI summary with threat prefixes

Enable GenAI notifications to get AI-written summaries when GenAI is available on your Frigate setup.

1. In integration options under **Appearance**, configure the global GenAI title prefixes:
   - Severity 0: (optional, often left blank)
   - Severity 1: ⚡
   - Severity 2+: ⚠️
2. In the profile's **Content & templates** section, expand the GenAI section and leave **Threat level prefix in title** enabled
3. In **Delivery & timing**, set the GenAI phase interruption level to "Passive" (arrives quietly)

**Result:** A notification arrives after the AI analysis:

- Title: "⚠️ Driveway - 3:15 PM" (if threat level 2+)
- Message: "Unknown person approached the front door and lingered for 45 seconds."

---

## Platform & delivery

### Different profiles for different people

Create multiple profiles on the same camera with different notify targets:

- **Profile 1**: "Driveway - Steve" targeting `notify.mobile_app_steve_iphone`, objects: all, severity: alert
- **Profile 2**: "Driveway - Sally" targeting `notify.mobile_app_sally_iphone`, objects: person only, severity: alert

Steve gets all alerts; Sally only gets person alerts.

### Silent updates with GIF

Configure the update phase for quiet animated previews:

In the profile's **Media & actions** section, configure the update phase:

- Attachment: Review GIF

In **Delivery & timing**, configure the update phase:

- Sound: `none`
- Volume: 0%
- Interruption: Passive

The update notification silently replaces the initial snapshot with an animated preview.

### Android phone notifications

Create a profile targeting an Android device:

**Basics:**

- Provider: Android (Companion)
- Device: select your Android phone

**Delivery & timing (Android delivery section):**

- Channel: `frigate_alerts` (create a matching channel on your phone via Companion App settings)
- Importance: `high`
- Sticky: On (notification stays until dismissed)

The integration emits both iOS and Android keys in every payload, so switching between providers requires no other changes.

### Family notify group

Send to multiple devices at once using a Home Assistant notify group:

1. Define a notify group in `configuration.yaml`:

   ```yaml
   notify:
     - name: family
       platform: group
       services:
         - service: mobile_app_steve_iphone
         - service: mobile_app_sally_pixel
   ```

2. In the profile's **Basics** step:
   - Provider: Cross-Platform (iOS + Android group)
   - Notify service: `notify.family`

Cross-Platform provider ensures both iOS and Android payload keys are included.

---

See [Getting Started](getting-started.md) for initial setup and [Troubleshooting](troubleshooting.md) if notifications aren't arriving.
