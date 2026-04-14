# Android

The Android Companion App supports notifications with images, video, action buttons, and persistent/sticky display.

## Settings

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

!!! note "Channel behavior"

    The `channel` and `importance` settings only take effect when the channel is first created on the device. To change importance after initial setup, delete the notification channel in Android Settings > Apps > Companion App > Notifications, then trigger a new notification.

## Media behavior

- **Images** are always sent as still snapshots (Android uses a separate `image` key from iOS). GIF attachments are sent as native GIFs -- animated on Android 14+, static on older versions.
- **Video** is sent as a direct MP4 URL (no HLS on Android). Review GIF video requests MP4 from Frigate; MP4 clips use the recorded clip directly.
- Android's video display extracts frames as a slideshow -- short previews (<10s) may not display well.
