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

!!! warning "Frigate URL reachability"

    The **Open Frigate** option uses the Frigate URL configured in [Global Defaults](global-defaults.md). Add-on users should select the ingress path, which routes through HA's proxy and works from any network. If you run Frigate externally, enter a URL reachable from your phone -- internal addresses (e.g. `http://10.0.0.5:5000`, Docker hostnames) will fail when you're outside your local network.

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

See [Profiles](profiles/index.md) for the full config flow field reference.

## Home Assistant actions

The integration registers these actions for scripts, automations, and Developer Tools.

| Action | What it does |
| -------- | ------------- |
| `frigate_notifications.silence_profile` | Silences a profile for `duration` minutes (or the profile default). Takes `profile_id`. |
| `frigate_notifications.clear_silence` | Clears a profile's silence timer. Takes `profile_id`. |
| `frigate_notifications.preview_notification` | Replays recent Frigate reviews through a profile and returns what each message would have sent. Never delivers. |
| `frigate_notifications.send_test_notification` | Replays one recent review through a profile and delivers the notifications it would have sent. |

### Replaying recent reviews

The integration keeps the last few Frigate reviews in memory (see the **Diagnostics** section in [Global Defaults](global-defaults.md)). The two replay actions run one of those reviews, message by message, through a profile's current templates and delay settings, so you can check what a profile sends without waiting for someone to walk in front of a camera.

Both actions take:

| Field | Description |
| ------- | ------------- |
| `entity_id` | The profile's **Enabled** switch. This is how the profile is selected. |
| `review_id` | A specific retained review. Defaults to the newest review on the profile's cameras. Review IDs are listed on the **Recent reviews** sensor. |
| `run_filters` | Evaluate the profile's filters for each message. Off by default. |
| `include_payload` | Add the full notify service data to each rendered row. Off by default, so rows show just what you would read on the device. |
| `title_template`, `message_template`, `subtitle_template` | Try a template (built-in ID or Jinja) in place of the profile's, in every phase. Handy for iterating on a template before saving it. |

`preview_notification` also takes `last`, the number of newest reviews to replay (1 to 10), and always returns a response. `send_test_notification` also takes `notify_service` to deliver somewhere other than the profile's target.

The response lists one row per retained message with an `outcome`:

| Outcome | Meaning |
| --------- | --------- |
| `rendered` | A notification would have been sent. The row carries `phase`, `fired_at`, title, message, subtitle, tag, group, click URL, and the notify service; with `include_payload` also the full service data, including media URLs. |
| `absorbed` | The message arrived while the initial notification was still waiting on its delay, so its data went into that notification instead. |
| `superseded` | A newer message replaced this one before its delay expired. |
| `skipped` | The phase is disabled on this profile. |
| `filtered` | The update carried none of the changes selected in the profile's update triggers. `detail` lists the selected triggers and what was new. |
| `rejected` | A filter rejected the message. `detail` names the filter and reason. Only with `run_filters`. |
| `render_error` | A template failed to render. `detail` has the error. |

Example, in Developer Tools > Actions (YAML mode):

```yaml
action: frigate_notifications.preview_notification
data:
  entity_id: switch.driveway_alerts_enabled
  last: 3
  run_filters: true
  message_template: "{{ subjects }} {{ zone_phrase }}{% if added_subject %}, {{ added_subject }} joined{% endif %}"
```

In a script, capture the result with `response_variable`.

!!! note "What replay does and does not model"

    Timing comes from the real gaps between Frigate's messages and the profile's current delays, so absorption into a delayed initial notification and update debouncing are reproduced. Filters that depend on Home Assistant state (time, presence, state, guard, silence, enabled switch) are evaluated against the state **now**, not at the time of the review; the response says `filters: evaluated_now`. Cooldown never rejects during a replay. A review that hit the retained-message cap is flagged `truncated`.

    Title and message templates that fail to render currently fall back to the raw template text instead of producing a `render_error` row.

!!! warning "Test sends are real notifications"

    `send_test_notification` delivers through the profile's real notify service with the real tag, so it can replace a live notification for the same review. Action buttons on a test notification work as usual, including **Silence**. Media links point at the event's own snapshot and clip, which stop working once Frigate's retention has expired. Android TV overlays have no tag or group, so replayed rows stack rather than replace.
