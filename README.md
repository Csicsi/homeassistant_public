# Home automation examples

This is a sanitized, static snapshot of selected home-automation patterns.
It is not a turnkey configuration and is not synchronized with the original
private installation.

Included:

- `ansible/`: generic Home Assistant discovery role with preflight, API,
  optional container inspection, and privacy-safe report generation.
- `esphome/`: an ESPHome device scaffold and a fuller Heltec/SX1262 DSL bridge
  example for four blinds. Hardware radio pins are documented; device name,
  Wi-Fi, API encryption, OTA credentials, and radio identity values remain
  secret-backed.
- `home-assistant/velux-package.example.yaml`: a generic Home Assistant package
  that exposes four blind controls through an ESPHome bridge.
- `floorplan/`: a renderer using synthetic demo geometry and positions.

No live hostnames, IP addresses, serial paths, Zigbee addresses, room layouts,
renders, credentials, or encrypted vault files are included. Replace every
`YOUR_...` value and validate the generated Home Assistant configuration before
using any example.

The DSL bridge example depends on the external
[`laberning/home_io_control`](https://github.com/laberning/home_io_control)
ESPHome component. Review and pin that dependency before a production build.
The `io_node_id` and `io_system_key` values are intentionally not included;
they must remain in the local ESPHome `secrets.yaml`.

The discovery role deliberately keeps raw API and terminal results in-memory
and marks those tasks `no_log`. Its generated public report contains endpoint
statuses only; container/serial inspection is disabled by default. Review local
reports before sharing them.

The floorplan renderer needs Blender with `bpy` available:

```text
blender -b -P floorplan/render_floorplan.py
```

It writes demo WebP files and `floorplan/positions.json` under this snapshot.
The synthetic OBJ is intentionally only a demonstration of the expected input
format.

## Snapshot policy

This repository is intentionally a one-time public snapshot. It is not a
support channel and may drift from the private source project.

Never add deployment data (hostnames, addresses, credentials, Zigbee or
radio identities) to this snapshot. See the subdirectory READMEs for usage
details.
