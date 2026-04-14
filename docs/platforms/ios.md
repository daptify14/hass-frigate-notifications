# iOS

The iOS Companion App supports rich notifications with images, GIFs, video, sound, and interactive actions.

## Settings

| Setting | Description | Options |
| --------- | ------------- | --------- |
| **Interruption level** | Controls how the notification appears. | `passive` (silent, no wake), `active` (default), `time-sensitive` (breaks Focus) |
| **Critical** | Overrides DND/silent mode. Separate toggle from interruption level. | Off |
| **Sound** | Notification sound name. | `default`, `none`, or a custom sound file |
| **Volume** | Sound volume. | `0.0` to `1.0` |
| **Attachment** | Image shown in the notification. | `thumbnail`, `snapshot`, `snapshot_bbox`, `snapshot_cropped`, `snapshot_cropped_bbox`, `review_gif`, `event_gif` |
| **Video** | Video attachment type. | HLS clip, MP4 clip, review GIF (as MP4 video), live view, or none |

!!! warning "Critical alerts"

    Critical alerts play sound at full volume regardless of the device's volume setting. Use sparingly -- iOS limits critical alert frequency.

## Media behavior

- **Snapshots and thumbnails** show as a still image in the notification
- **Review GIF / Event GIF** shows as an animated image (expand notification to view)
- **Review GIF video** requests the review preview as MP4 from Frigate, giving iOS video player controls (play/pause). Only available for review previews -- Frigate's event preview endpoint always returns GIF and does not support MP4 conversion.
- **Live view** (iOS only) opens the camera's live stream directly in the notification. Uses the `camera.<camera_name>` entity from Home Assistant. Not available on Android or Android TV.
- **HLS video** streams the Frigate clip (requires Frigate integration's media proxy)
- **MP4 clip** plays the recorded clip as an MP4 video

!!! tip "HLS vs MP4"

    HLS clips stream progressively and begin playback almost immediately when expanding the notification. MP4 clips must download the entire file before playback starts, which can mean a noticeable delay on longer clips depending on network conditions. **HLS is recommended for iOS.** MP4 is the only option on Android.
