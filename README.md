# Reminder Light

Reminder Light is a custom Home Assistant integration that turns a selected light
into a visible reminder display. The integration owns reminder schedules, due
state, color, and light output while reusing existing Home Assistant entities as
completion signals.

> [!IMPORTANT]
> Reminder Light is an early `0.x` project. Back up your Home Assistant
> configuration before testing and expect configuration changes between releases.

## Current MVP

- Configure one daily reminder through the Home Assistant UI.
- Select a Home Assistant light, reminder color, brightness, and due time.
- Complete the reminder when any selected entity reaches a target state.
- Complete the reminder manually with the generated button entity.
- Observe due state through the generated binary sensor.
- Restore reminder state after a Home Assistant restart.

The completion entity can be a button, motion sensor, contact sensor, switch, or
any other Home Assistant entity. Reminder Light listens only for the configured
state change and does not communicate with the underlying hardware protocol.

## Install for testing

### HACS custom repository

1. In HACS, open the menu and choose **Custom repositories**.
2. Add `https://github.com/coltmort/reminder-light` as an **Integration**.
3. Install Reminder Light and restart Home Assistant.
4. Open **Settings > Devices & services > Add integration** and search for
   **Reminder Light**.

The repository must be accessible to the GitHub account used by HACS while it is
private. Public releases can be installed without private-repository access.

### Manual installation

Copy `custom_components/reminder_light` into the `custom_components` directory
inside your Home Assistant configuration directory, restart Home Assistant, and
add the integration from **Settings > Devices & services**.

## Configure the first reminder

Choose an output light and shared brightness, then define the first reminder:

- **Reminder time** uses local Home Assistant time in 24-hour `HH:MM` format.
- **Reminder color** uses a hexadecimal color such as `#00AEEF`.
- **Completion entity** is an existing Home Assistant entity.
- **Completion state** is the exact target state, such as `on`, `open`, or a
  device-specific value shown in Developer Tools.

At the scheduled time, Reminder Light marks the reminder due and turns on the
selected light. A matching completion state, or pressing the generated complete
button, clears the reminder and turns off the light.

## Development

The integration is contained in `custom_components/reminder_light/`. Keep all
runtime files required by Home Assistant inside that directory so both HACS and
manual installation work consistently.

Before committing a change:

```bash
python3 -m compileall custom_components/reminder_light
python3 -m json.tool custom_components/reminder_light/manifest.json
python3 -m json.tool hacs.json
```

GitHub Actions run HACS and Home Assistant `hassfest` validation on pushes and
pull requests.

## Releases

Reminder Light follows semantic versioning. During `0.x`, minor releases may
contain breaking configuration changes.

1. Update `version` in `custom_components/reminder_light/manifest.json`.
2. Commit the release change.
3. Create and push a matching tag prefixed with `v`, such as `v0.1.0`.

The release workflow verifies that the tag matches the manifest version, builds
`reminder_light.zip`, and publishes a GitHub release. HACS can install tagged
releases or the default branch for development testing.

## License

Reminder Light is available under the [MIT License](LICENSE).
