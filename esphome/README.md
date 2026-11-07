# ESPHome examples

## DSL bridge

[velux-dsl-bridge.example.yaml](./velux-dsl-bridge.example.yaml) demonstrates
the Heltec WiFi LoRa 32 V3 / SX1262 wiring and four one-way Somfy-style blind
identities used by the `home_io_control` external component.

The blind IDs are part of the enrollment identity. Do not rename an ID after
enrollment. Enroll one blind at a time according to the hardware/component
procedure.

The example intentionally leaves the following values in `!secret` references:

- Wi-Fi and fallback AP passwords
- ESPHome API encryption key
- OTA password
- `io_node_id`
- `io_system_key`

See [secrets.yaml.example](./secrets.yaml.example) for the local secret names.
Do not copy real values into the repository.

The external component is referenced from
[`laberning/home_io_control`](https://github.com/laberning/home_io_control).
Review the component and pin a known-good revision before production use.

## Generic scaffold

[velux-bridge.example.yaml](./velux-bridge.example.yaml) is a smaller,
hardware-neutral scaffold. It is not a replacement for the DSL component and
does not contain a guessed radio implementation.
