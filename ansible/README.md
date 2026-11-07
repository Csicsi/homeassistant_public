# Ansible discovery role

The `ha_discover` role performs read-only discovery against a Home Assistant
installation:

1. Preflight API, web, and optional SSH connectivity checks.
2. API-level status and registry requests.
3. Optional Home Assistant CLI, add-on, config-directory, and serial-path
   inspection over SSH.
4. Local Markdown and JSON report generation.

The example playbook uses `HOME_ASSISTANT_TOKEN` from the controller
environment. It does not put a token in inventory.

```sh
export HOME_ASSISTANT_TOKEN='replace-locally'
ansible-playbook \
  -i inventories/homeassistant.example.yml \
  playbooks/discover.example.yml
```

By default, the container/serial inspection is disabled. Enable it explicitly
with `-e ha_discover_include_container_inventory=true` only when the SSH target
is trusted and the resulting local report will be reviewed before sharing.

The role uses `no_log` for authenticated requests and does not include raw API
or terminal data in its generated public report. `validate_certs: true` is
intentional; use a trusted CA rather than disabling certificate validation.
