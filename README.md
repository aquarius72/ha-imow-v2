# ha-imow-v2 — STIHL iMow Gen5+ for Home Assistant

A native Home Assistant custom integration for **STIHL iMow Gen5+ mowers** (including Evo variants) that do not work with the original [stihl_imow](https://www.home-assistant.io/integrations/stihl_imow/) integration.

[![HACS Badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

---

## Features

- Live mower status: job state, overall state, battery level
- GPS coordinates (latitude / longitude) from the STIHL cloud
- Active job start and end times
- Next scheduled mowing start — computed from the mower's weekly calendar
- Current mowing area
- Rain sensor state
- Remote commands: Start, Stop, Park (via HA services or button entities)
- Configurable poll interval (default 10 minutes)
- HACS-installable

## Supported Mowers

All STIHL iMow models on the **Gen5+ platform** (myimow.stihl.com):

- iMow® 5 / iMow® 5 EVO
- iMow® 6 / iMow® 6 EVO ✅ *(tested)*
- iMow® 7 / iMow® 7 EVO

Other Gen5+ models should work but are untested. Feedback welcome via [Issues](https://github.com/aquarius72/ha-imow-v2/issues).

> Legacy models using `oauth2.imow.stihl.com` are **not** supported.

---

## Installation via HACS

1. Open HACS in your Home Assistant instance.
2. Go to **Integrations → Custom repositories**.
3. Add `https://github.com/aquarius72/ha-imow-v2` as an **Integration**.
4. Search for **STIHL iMow v2** and click **Install**.
5. Restart Home Assistant.

## Manual Installation

```
custom_components/imow_v2/  →  config/custom_components/imow_v2/
```

Restart Home Assistant.

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **STIHL iMow v2**.
3. Enter your **myimow.stihl.com** email and password.
4. Done — your mower(s) appear as devices with all sensors.

**Options** (after setup): adjust the poll interval (1–60 minutes).

---

## Entities

Entity IDs are derived from your mower's name. For example, a mower named **"Robin"** produces `sensor.robin_job_state`, `sensor.robin_battery`, etc. The table below uses `<mower>` as a placeholder.

### Sensors
| Entity | Description |
|--------|-------------|
| `sensor.<mower>_job_state` | Current job state (`plannedJobRunning`, `docked`, …) |
| `sensor.<mower>_overall_state` | Overall mower state |
| `sensor.<mower>_state_short` | State short message |
| `sensor.<mower>_state_detail` | State detail message |
| `sensor.<mower>_error_code` | Current error code |
| `sensor.<mower>_battery` | Battery level (%) |
| `sensor.<mower>_gps_latitude` | GPS latitude |
| `sensor.<mower>_gps_longitude` | GPS longitude |
| `sensor.<mower>_job_start_time` | Active job start timestamp |
| `sensor.<mower>_job_end_time` | Active job end timestamp |
| `sensor.<mower>_next_scheduled_start` | Next scheduled start (computed from calendar) |
| `sensor.<mower>_last_seen` | Last cloud contact timestamp |
| `sensor.<mower>_area` | Current mowing area (m²) |
| `sensor.<mower>_firmware` | Firmware version |
| `sensor.<mower>_total_operating_time` | Total operating time |
| `sensor.<mower>_total_distance` | Total distance travelled (km) |
| `sensor.<mower>_blade_operating_time` | Total blade operating time |

### Binary Sensors
| Entity | Description |
|--------|-------------|
| `binary_sensor.<mower>_online` | Cloud connectivity |
| `binary_sensor.<mower>_rain_sensor` | Rain detected |
| `binary_sensor.<mower>_blade_service` | Blade service required |
| `binary_sensor.<mower>_gps_protection` | GPS protection active |
| `binary_sensor.<mower>_child_lock` | Child lock active |
| `binary_sensor.<mower>_automatic_mode` | Automatic mode enabled |

### Number
| Entity | Description |
|--------|-------------|
| `number.<mower>_default_mowing_duration` | Default mowing duration (minutes) — used by Start commands |

### Device Tracker
| Entity | Description |
|--------|-------------|
| `device_tracker.<mower>_location` | GPS position on the HA map |

---

## Services

### `imow_v2.intent`

Send any command to the mower.

| Field | Required | Description |
|-------|----------|-------------|
| `action` | yes | `start-mowing`, `pause`, `resume`, `end-job-and-return-to-dock`, `toDocking`, `edgeMowing`, `startMowingFromPoint` |
| `mower_device` | one of | HA device ID |
| `mower_name` | one of | Friendly mower name |
| `startpoint` | no | Zone index for `startMowingFromPoint` |

Friendly aliases also accepted for `action`: `startMowing`, `stop_mowing`, `park`, `edge`.

---

## Credits

Authentication and API reverse-engineering based on the excellent work of **TA2k** in [ioBroker.iMow](https://github.com/TA2k/ioBroker.iMow).
Modifications and Python port by [aquarius72](https://github.com/aquarius72).

## License

MIT — see [LICENSE](LICENSE)
