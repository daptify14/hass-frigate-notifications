# Notification Providers

Each notification profile targets a specific provider that determines how notifications are built and delivered. You choose the provider in the **Basics** step of the profile wizard.

## Provider types

| Provider | Platform | App | Use when |
| ---------- | ---------- | ----- | ---------- |
| **Apple (iOS Push)** | iPhone / iPad | HA Companion App | All recipients use Apple devices |
| **Android (Companion)** | Android phones / tablets | HA Companion App | All recipients use Android devices |
| **Cross-Platform** | iOS + Android | HA Companion App | Target is a notify group with both platforms |
| **Android TV / Fire TV** | Android TV / Fire TV | Notifications for Android TV | TV overlay notifications |

Apple, Android, and Cross-Platform all use the same mobile app provider internally. The payload includes both iOS and Android keys in every notification -- each companion app ignores keys it doesn't understand. The provider selection affects which platform-specific options appear in the config flow and which action URIs are resolved.

## Apple (iOS Push)

The iOS Companion App supports rich notifications with images, GIFs, video, sound, and interactive actions.

### iOS settings

| Setting | Description | Options |
| --------- | ------------- | --------- |
| **Interruption level** | Controls how the notification appears. | `passive` (silent, no wake), `active` (default), `time-sensitive` (breaks Focus) |
| **Critical** | Overrides DND/silent mode. Separate toggle from interruption level. | Off |
| **Sound** | Notification sound name. | `default`, `none`, or a custom sound file |
| **Volume** | Sound volume. | `0.0` to `1.0` |
| **Attachment** | Image shown in the notification. | `thumbnail`, `snapshot`, `snapshot_bbox`, `snapshot_cropped`, `snapshot_cropped_bbox`, `review_gif`, `event_gif` |
| **Video** | Video attachment type. | HLS clip, MP4 clip, review GIF (as MP4 video), live view, or none |

> **Note:** Critical alerts play sound at full volume regardless of the device's volume setting. Use sparingly -- iOS limits critical alert frequency.

### iOS media behavior

- **Snapshots and thumbnails** show as a still image in the notification
- **Review GIF / Event GIF** shows as an animated image (expand notification to view)
- **Review GIF video** requests the review preview as MP4 from Frigate, giving iOS video player controls (play/pause). Only available for review previews -- Frigate's event preview endpoint always returns GIF and does not support MP4 conversion.
- **Live view** (iOS only) opens the camera's live stream directly in the notification. Uses the `camera.<camera_name>` entity from Home Assistant. Not available on Android or Android TV.
- **HLS video** streams the Frigate clip (requires Frigate integration's media proxy)
- **MP4 clip** plays the recorded clip as an MP4 video

> **HLS vs MP4:** HLS clips stream progressively and begin playback almost immediately when expanding the notification. MP4 clips must download the entire file before playback starts, which can mean a noticeable delay on longer clips depending on network conditions. **HLS is recommended for iOS.** MP4 is the only option on Android.

## Android (Companion)

The Android Companion App supports notifications with images, video, action buttons, and persistent/sticky display.

### Android settings

| Setting | Description | Default |
| --------- | ------------- | --------- |
| **Channel** | Android notification channel name. | (none) |
| **Importance** | Channel importance level. | `high` |
| **Priority** | Delivery priority. | `high` |
| **TTL** | Time to live (seconds). | `0` |
| **Sticky** | Notification stays until manually dismissed. | Off |
| **Persistent** | Notification cannot be swiped away. | Off |
| **Android Auto** | Show on Android Auto displays. | Off |
| **Color** | Notification accent color (hex). | (none) |

> **Note:** The `channel` and `importance` settings only take effect when the channel is first created on the device. To change importance after initial setup, delete the notification channel in Android Settings > Apps > Companion App > Notifications, then trigger a new notification.

### Android media behavior

- **Images** are always sent as still snapshots (Android uses a separate `image` key from iOS). GIF attachments are sent as native GIFs -- animated on Android 14+, static on older versions.
- **Video** is sent as a direct MP4 URL (no HLS on Android). Review GIF video requests MP4 from Frigate; MP4 clips use the recorded clip directly.
- Android's video display extracts frames as a slideshow -- short previews (<10s) may not display well.

## Android TV / Fire TV

Android TV uses the separate [Notifications for Android TV](https://www.home-assistant.io/integrations/nfandroidtv/) integration (not the Companion App). Notifications appear as a screen overlay.

### TV overlay settings

| Setting | Description | Default |
| --------- | ------------- | --------- |
| **Position** | Overlay position on screen. | `bottom-right` |
| **Font size** | Text size. | `medium` |
| **Duration** | How long the overlay stays visible (seconds). | `5` |
| **Transparency** | Overlay background transparency. | `0%` |
| **Interrupt** | Whether to interrupt current playback. | Off |
| **Timeout** | Provider timeout (seconds). | `30` |
| **Color** | Overlay accent color. | (none) |

### Limitations

- **Still images only** -- GIF and video attachments fall back to a cropped snapshot. The Android TV integration does not support animated media.
- **No action buttons** -- TV overlays cannot display interactive actions.
- **No grouping or tagging** -- each notification is an independent overlay; there's no notification history or stacking.

## Cross-Platform / notify groups

Use the **Cross-Platform** provider when your notify target is a Home Assistant [notify group](https://www.home-assistant.io/integrations/group/#notify-groups) that includes both iOS and Android devices. The integration sends both sets of platform keys, and each device uses what it understands.

To set up a notify group:

```yaml
# configuration.yaml
notify:
  - platform: group
    name: family_phones
    services:
      - service: mobile_app_iphone
      - service: mobile_app_pixel
```

Then in the profile's **Basics** step, set the notify service to `notify.family_phones`.

See [Actions](actions.md) for action button presets, tap actions, and platform differences.

## Choosing a provider

- **Single phone**: use Apple or Android to match your device
- **Family with mixed devices**: create a notify group and use Cross-Platform
- **TV dashboard**: use Android TV for ambient overlay alerts
- **Multiple profiles**: you can create separate profiles per device with different presets -- e.g., a Snapshot Only for your phone and a Silent Log for the TV
