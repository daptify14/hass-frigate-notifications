# Notification Lifecycle

Notifications for Frigate follows each Frigate review through four lifecycle phases. Each phase can trigger a notification with independently configured behavior.

## Lifecycle phases

The integration maps Frigate's MQTT message types to notification phases:

| MQTT message | Notification phase | Description |
|-------------|-------------------|-------------|
| new | **initial** | Frigate created a new review |
| update | **update** | Frigate added objects, zones, or detections to a review |
| end | **end** | Frigate closed the review |
| genai | **genai** | Frigate's Gen AI Review Summary completed |

The initial phase fires on the **first message that passes filters** for a review. Normally that's the `new` message, but if a filter isn't satisfied yet (e.g., the required zone hasn't been detected), the `new` message is skipped and the first `update` that passes filters dispatches as the initial notification instead.

> **Tip:** Templates receive the phase value via `{{ phase }}`, not the raw MQTT message type. So the first notification always uses `phase = "initial"`, even if it was triggered by an `update` message.

The descriptions below reflect the default preset behavior. Each phase is fully configurable -- sound, attachment, video, delay, interruption level, and more can be changed per phase in your profile settings.

### Initial

Fires on Frigate's `new` message, or a later `update` if filters (like zone or object) weren't satisfied yet. Sends an audible notification with a snapshot. A configurable initial delay (1.0s) gives Frigate time to refine the snapshot and detect zones before the notification fires.

### Update

Sends a silent notification with a GIF when Frigate adds objects, zones, or detections to an ongoing review.

### End

Sends a silent notification with a GIF of the complete review. 5s delay gives Frigate time to finalize the clip.

### GenAI

Sends the AI-generated review summary. When GenAI is available/enabled for any camera selected for profile, the phase is enabled by default; when absent, GenAI sections are hidden. It can also be toggled per-profile in the Content step.

## How dispatch works

### Initial delay and absorption

When the initial notification is triggered, the dispatcher waits for the configured initial delay before sending. During this window:

- Incoming updates are absorbed silently -- the review data is updated in-place
- The pending notification reads the latest data when it finally fires
- A rapid sequence like `new → update → update` within the delay window produces a single notification with the most current data

This gives Frigate time to refine snapshots and detect zone transitions before the first notification goes out.

### Update and end debouncing

After the initial notification, each `update` or `end` event schedules a delayed task. If a new event arrives while a task is pending, the old task is cancelled and replaced. This debounces rapid updates into a single notification.

### GenAI independence

GenAI notifications run on a completely independent track:

- Never cancel pending initial/update/end tasks
- Are never cancelled by initial/update/end tasks
- Use their own phase config and delay
- Can fire while other tasks are pending or after end has been sent
- Phase-enabled gating is handled by the dispatcher (same as initial/update/end), not the filter chain

## Stale review cleanup

Reviews that have not received an update in 30 minutes are automatically removed by a periodic cleanup timer (runs every 5 minutes). This recovers resources if Frigate's review lifecycle was interrupted by network loss, Frigate restart, or similar. Associated per-profile dispatch state is also cleaned up.

## Silence

Silence temporarily mutes a [profile](../configuration/profiles.md). It is per-profile, time-based -- when the timer expires, notifications resume automatically.

**Triggering silence:**

- Tap the **Silence Notifications** action button on any notification (silences the sending profile)
- Press the **Silence** button entity on the profile's device
- Set the **Silenced Until** datetime entity directly from a dashboard or automation

Silence is **persistent** -- it survives restarts. To clear immediately, press **Clear Silence** or set the datetime to a past time. See [Profiles -- Entities](../configuration/profiles.md#entities) for the full entity list.

## Cooldown

Cooldown enforces a minimum interval between initial notifications for a given profile on a given camera.

- Only gates initial notifications -- in-flight update/end/genai notifications bypass cooldown
- Tracked per (profile, camera) pair -- different cameras on the same profile have independent windows
- **In-memory only** -- does not survive restarts

### Example

With a 60-second cooldown on "Driveway Alerts":

| Time | Event | Result |
|------|-------|--------|
| 3:00:00 PM | Person detected on driveway | Sent -- cooldown starts |
| 3:00:15 PM | Update with zone info | Sent -- updates bypass cooldown |
| 3:00:30 PM | Car detected on driveway (new review) | **Blocked** -- 30s remaining |
| 3:01:05 PM | Another person on driveway (new review) | Sent -- cooldown expired |

## Alert once

When enabled, only the first notification per review plays sound. Subsequent update/end/genai notifications are delivered silently. Critical notifications override this and always play sound. On Android, this sets the native `alert_once` flag.

## Silence vs cooldown

| | Silence | Cooldown |
|---|---------|----------|
| **Triggered by** | User (action button, entity, automation) | Automatic |
| **Scope** | Entire profile (all cameras) | Per (profile, camera) pair |
| **Affects** | All phases | Only initial notifications |
| **Survives restart** | Yes (entity-based) | No (in-memory) |

Duration defaults and per-profile overrides are configured in [Delivery & timing](../configuration/profiles.md#delivery--timing).
