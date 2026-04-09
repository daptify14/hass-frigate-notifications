# Actions

Notifications for Frigate supports three types of actions on notifications: action buttons, tap action, and custom actions (inline HA action sequences).

## Action buttons

Each notification can display up to three action buttons. You configure these in the profile's **Media & actions** section under the **Action buttons** subsection. Buttons are selected from a list of presets.

### Available presets

| Preset | What it does | Platform notes |
| -------- | ------------- | ---------------- |
| **View Clip** | Opens the video clip for this event | HLS stream on iOS, MP4 on Android |
| **View Snapshot** | Opens the full-resolution snapshot | Same on all platforms |
| **View GIF** | Opens the animated review preview | Same on all platforms |
| **View Live Stream** | Opens the camera's live proxy stream | Same on all platforms |
| **Silence Notifications** | Mutes this profile for the configured silence duration | See [Notification Lifecycle](notification-lifecycle.md#silence) |
| **Open HA (App)** | Navigates to `/lovelace` inside the Companion App | In-app navigation |
| **Open HA (Browser)** | Opens your HA instance URL in the browser | Full URL navigation |
| **Open Frigate** | Opens your Frigate UI | URL configured in [Global Defaults](global-defaults.md) |
| **Custom Action** | Fires the profile's button-press custom action | See [Custom actions](#custom-actions) below |
| **No Action (Android)** | Suppresses the button (no visible button rendered) | |
| **None (empty slot)** | Leaves the slot empty | |

**Defaults:** View Clip, View Snapshot, Silence Notifications.

All media URLs go through Frigate's media proxy in Home Assistant and include multi-instance support via the `client_id` path segment.

### Platform differences

- **iOS**: buttons display with SF Symbol icons and support destructive styling (red button for Silence)
- **Android**: buttons display without icons; video links use MP4 instead of HLS
- **Android TV**: no action buttons -- TV overlays cannot display interactive actions

## Tap action

The tap action controls what happens when the user taps the notification body itself (not a button). Configure it in the profile's **Media & actions** section under the **Tap action** subsection.

### Available options

| Option | What it does |
| -------- | ------------- |
| **View Clip** | Opens the video clip (default) |
| **View Snapshot** | Opens the snapshot |
| **View GIF** | Opens the review preview GIF |
| **View Live Stream** | Opens the camera's live stream |
| **Open HA (App)** | Navigates to `/lovelace` in the app |
| **Open HA (Browser)** | Opens HA in the browser |
| **Open Frigate** | Opens the Frigate UI |
| **No Action** | Suppresses the default tap behavior |

**Default:** View Clip.

> **Frigate URL reachability:** The **Open Frigate** option uses the Frigate URL configured in [Global Defaults](global-defaults.md). Add-on users should select the ingress path, which routes through HA's proxy and works from any network. If you run Frigate externally, enter a URL reachable from your phone -- internal addresses (e.g. `http://10.0.0.5:5000`, Docker hostnames) will fail when you're outside your local network.

## Custom actions

Custom actions let you trigger Home Assistant action sequences (lights, TTS, scripts, etc.) directly from your notification profile -- no separate automation required.

### 5 action slots

There are five places to attach custom actions, four that fire automatically and one triggered by button press:

| Slot | Trigger | Config location | Example use case |
| ------ | --------- | ---------------- | ------------------ |
| **On Initial** | Auto-fires after initial notification sends | Media & actions (Custom actions section) | Turn on porch light, play TTS alert |
| **On Update** | Auto-fires after update notification sends | Media & actions (Custom actions section) | Escalate alert, flash lights |
| **On End** | Auto-fires after end notification sends | Media & actions (Custom actions section) | Turn off lights, log event |
| **On GenAI** | Auto-fires after AI summary notification sends | Media & actions (Custom actions section) | Forward summary to Slack or TTS |
| **On Button Press** | User taps the "Custom Action" button | Media & actions (Custom button action section) | Lock door, trigger siren, acknowledge |

All slots are optional. Leave them empty to skip.

### How custom actions work

- Actions are configured using Home Assistant's visual **Action selector** in the config flow -- the same builder used in automations and scripts.
- Phase actions (initial, update, end, genai) execute automatically after a successful notification send for that phase.
- The button-press action executes when the user taps the "Custom Action" button on the notification. To use it, set one of the three action button slots to **Custom Action** in the Media & actions section.
- Actions receive the full template context (camera, object, zone, review_id, genai_summary, etc.) as variables, so you can use them in action data templates.
- Action errors are logged but never crash the integration or block notification delivery.

### Button press context

When a user taps a notification button, the integration looks up the review in its cache to provide full context variables. Reviews are cached for 30 minutes after the last MQTT update. If the review has expired (stale cleanup), the action still executes but with minimal context (camera and profile ID only). Most button-press actions (turn on a light, trigger a script) don't need review-specific variables.

See [Profiles](profiles.md) for the full config flow field reference.
