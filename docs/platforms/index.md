# Platforms

Each notification profile targets a specific provider that determines how notifications are built and delivered. You choose the provider in the **Basics** step of the profile wizard.

## Provider comparison

| Provider | Platform | App | Use when |
| ---------- | ---------- | ----- | ---------- |
| **Apple (iOS Push)** | iPhone / iPad | HA Companion App | All recipients use Apple devices |
| **Android (Companion)** | Android phones / tablets | HA Companion App | All recipients use Android devices |
| **Cross-Platform** | iOS + Android | HA Companion App | Target is a notify group with both platforms |
| **Android TV / Fire TV** | Android TV / Fire TV | Notifications for Android TV | TV overlay notifications |

Apple, Android, and Cross-Platform all use the same mobile app provider internally. The payload includes both iOS and Android keys in every notification -- each companion app ignores keys it doesn't understand. The provider selection affects which platform-specific options appear in the config flow and which action URIs are resolved.

## Choosing a provider

- **Single phone**: use [Apple (iOS)](ios.md) or [Android](android.md) to match your device
- **Family with mixed devices**: create a notify group and use Cross-Platform (see below)
- **TV dashboard**: use [Android TV](android-tv.md) for ambient overlay alerts
- **Multiple profiles**: you can create separate profiles per device with different presets -- e.g., a Snapshot Only for your phone and a Silent Log for the TV

## Cross-Platform / notify groups

Use the **Cross-Platform** provider when your notify target is a Home Assistant [notify group](https://www.home-assistant.io/integrations/group/#notify-groups) that includes both iOS and Android devices. The integration sends both sets of platform keys, and each device uses what it understands.

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
