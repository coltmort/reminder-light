# Reminder Light

[![Open your Home Assistant instance and open Reminder Light in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=coltmort&repository=reminder-light&category=integration)

Reminder Light turns a Home Assistant light into a shared visual reminder
display. It owns task schedules, due state, colors, and display rotation while
using Home Assistant's native trigger system to decide when a task is complete.

> [!IMPORTANT]
> Reminder Light is an early `0.x` project. Back up your Home Assistant
> configuration before testing and expect configuration changes between releases.

## Features

- Create and manage multiple reminders from **Settings > Devices & services >
  Reminder Light**.
- Schedule each task on selected weekdays at up to six times per day.
- Use native Home Assistant state, device, event, time, or other triggers as
  completion signals. This includes physical button presses when the button's
  integration exposes a device trigger.
- Pick a color for every task. If several reminders are due, the selected light
  rotates through their colors.
- View all enabled reminder occurrences in the generated **Reminder Light
  schedule** calendar entity and add it to Home Assistant's Calendar dashboard.
- Complete any due task manually with its generated button entity.
- Observe due state through a generated binary sensor.
- Restore reminder state after Home Assistant restarts.

Reminder Light does not communicate with Zigbee, Z-Wave, Bluetooth, or other
hardware protocols directly. Those devices remain owned by their existing Home
Assistant integrations.

## Install with HACS

1. Use the **Open your Home Assistant** button above, or open HACS and choose
   **Custom repositories**.
2. Add `https://github.com/coltmort/reminder-light` as an **Integration**.
3. Open Reminder Light in HACS and download the latest release.
4. Restart Home Assistant.
5. Open **Settings > Devices & services > Add integration** and search for
   **Reminder Light**.

Reminder Light currently requires Home Assistant `2026.9.0` or newer.

## Set up reminders

Initial setup asks only for the shared display:

- **Reminder light** is the light used to show due task colors.
- **Color rotation interval** controls how often the color changes when multiple
  tasks are due.
- **Reminder brightness** is used whenever the integration turns on the light.

The first reminder form opens immediately afterward. Later, open **Settings >
Devices & services > Reminder Light** and use **Add entry** to create another
reminder. Each reminder entry can be reconfigured or deleted from that page.

For completion, choose **Add trigger**. The editor is the same trigger editor
used by Home Assistant automations. For a physical button, prefer its **Device**
trigger and select the press action. If it has no device trigger but exposes an
event entity, use a state trigger for that entity instead. Completion triggers
only act while their reminder is due.

## Weekly calendar

After setup, Home Assistant creates `calendar.reminder_light_schedule` (the
entity ID may differ if a similarly named entity already exists). Add it to the
built-in Calendar dashboard to see the week. Selecting an occurrence shows its
schedule and current status; editing remains on the Reminder Light integration
page so schedule changes go through Home Assistant's validated configuration
flow.

## Upgrading from 0.1.0

Version 0.2.0 migrates the original reminder into a reminder entry, keeps its
persisted due/completed state, converts its entity/state completion rule into a
native state trigger, and keeps the original due sensor and complete-button
unique IDs. Restart Home Assistant after updating through HACS.

## Manual installation

Copy `custom_components/reminder_light` into the `custom_components` directory
inside your Home Assistant configuration directory, restart Home Assistant, and
add the integration from **Settings > Devices & services**.

## Development and releases

The integration is contained in `custom_components/reminder_light/`. GitHub
Actions run HACS and Home Assistant hassfest validation on pushes and pull
requests.

Before committing a change:

```bash
python3 -m compileall custom_components/reminder_light
python3 -m json.tool custom_components/reminder_light/manifest.json
python3 -m json.tool hacs.json
```

Reminder Light follows semantic versioning. A tag such as `v0.2.0` must match
the version in `manifest.json`. Pushing the tag builds `reminder_light.zip` and
publishes a GitHub release; HACS installs that release archive.

## License

Reminder Light is available under the [MIT License](LICENSE).
