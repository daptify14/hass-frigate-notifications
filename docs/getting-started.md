# Getting Started

This guide walks you through creating your first notification profile after [installing](installation.md) the integration.

## Set your base URLs

Before creating a profile, make sure your Home Assistant and Frigate URLs are set. These are used for notification attachments and the "Open Frigate" action button.

1. Go to Settings > Devices & Services > Notifications for Frigate
2. Click the settings cog (**Configure**) on the integration entry
3. Set your **Home Assistant URL** and **Frigate URL** in the Delivery Defaults step
4. Click through the remaining steps (the defaults are fine to start with)

> **Tip:** You can come back and adjust shared defaults anytime. Saving the options automatically reloads the integration and applies the updated defaults.

## Create a notification profile

1. Go to Settings > Devices & Services > Notifications for Frigate
2. Click **Add notification profile**
3. The wizard starts with two required steps, then opens a menu for optional customization:

### Preset

Pick a starting template. **Live Alerts** is the recommended default: instant alert with a snapshot, GIF follow-up, and optional AI summary. Every value the preset sets is fully editable afterward.

### Basics

Give the profile a name (e.g., "Driveway Alerts") and select one or more Frigate cameras. Choose your platform: Apple (iOS Push), Android (Companion), Cross-Platform (iOS + Android group), or Android TV / Fire TV. After pressing next, the step reloads for you to pick the target device or notify service (group or TV), tag template, and group template.

### Customize (optional)

After Basics, you land on a menu with these sections:

- **Filtering**: object types, severity, required zones, recognition filters
- **Content**: message and subtitle templates per phase, zone phrases
- **Media & Actions**: attachments (snapshot, GIF), tap action, action buttons per phase
- **Delivery**: sound, volume, interruption level, delays per phase
- **Save**: save the profile as-is

If the preset defaults work for you, go straight to **Save**. Profiles can be reconfigured later as well to customize further.

## Test it

Trigger a detection on the camera you configured (walk in front of it) and check your phone for the notification. If it doesn't arrive, see [Troubleshooting](troubleshooting.md).

## Next steps

Once your first profile is working:

- **Add more profiles** for different cameras or notification targets
- **Adjust filters** for time windows, presence, or entity state (e.g., only notify when the alarm is armed)
- **Customize templates** with zone phrases and context variables for richer messages
- **Enable GenAI** for AI-generated review summaries as a fourth notification phase
