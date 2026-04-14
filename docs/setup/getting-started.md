# Getting Started

This guide walks you through creating your first notification profile after [installing](installation.md) the integration.

## Set your base URLs

Before creating a profile, make sure your Home Assistant and Frigate URLs are set. These are used for notification attachments and the "Open Frigate" action button.

1. Go to Settings > Devices & Services > Notifications for Frigate
2. Click the settings cog (**Configure**) on the integration entry
3. Set your **Home Assistant URL** and **Frigate URL** in the Delivery Defaults section
4. Click through the remaining sections (the defaults are fine to start with)

> **Tip:** You can come back and adjust shared defaults anytime. Saving the options automatically reloads the integration and applies the updated defaults.

## Create a notification profile

1. Go to Settings > Devices & Services > Notifications for Frigate
2. Click **Add notification profile**
3. The wizard starts with two required steps, then opens a menu for optional customization:

### Preset

Pick a starting template. **Live Alerts** is the recommended default: instant alert with a snapshot, GIF follow-up, and optional AI summary. All values are editable after creation.

### Basics

Give the profile a name (e.g., "Driveway Alerts") and select one or more Frigate cameras. Choose your platform: Apple (iOS Push), Android (Companion), Cross-Platform (iOS + Android group), or Android TV / Fire TV. After pressing next, the step reloads for you to pick the target device or notify service, tag template, and group template.

### Customize (optional)

After Basics, you land on a menu with these sections:

- **Filtering** -- objects, zones, guard, time, presence, state
- **Content & templates** -- message templates, subtitles, emoji, zone phrases
- **Media & actions** -- attachments, video, action buttons
- **Delivery & timing** -- sound, timing, rate limiting, platform options
- **Save profile** -- save with current settings

If the preset defaults work for you, go straight to **Save**. You can reconfigure any section later from the profile device's three-dot menu.

See [Profiles](../reference/profiles.md) for a full reference of every field.

## Test it

Trigger a detection on the camera you configured (walk in front of it) and check your phone for the notification. If it doesn't arrive, see [Troubleshooting](../troubleshooting.md).

## Next steps

Once your first profile is working:

- **Add more profiles** for different cameras or notification targets
- **Adjust filters** for time windows, presence, or entity state (e.g., only notify when the alarm is armed)
- **Customize templates** with zone phrases and context variables for richer messages
- **Enable GenAI** for AI-generated review summaries as a fourth notification phase
