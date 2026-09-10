# Geyser Pasteurization

A Home Assistant custom integration that manages Legionella pasteurization/disinfection cycles for a hybrid hot water (geyser) system — designed for setups where solar PV diversion causes irregular, sometimes-too-low water temperatures that let bacteria proliferate.

It watches a temperature sensor over a rolling window, and if the water hasn't reliably reached and held a safe disinfection temperature, it automatically (or manually) engages a heater entity, holds it at temperature for a required duration, and logs the result — with a hard failsafe timeout so it can never run away.

## Why this exists

Hybrid geysers with solar diversion heat opportunistically: whenever there's excess PV, the electric element kicks in, and whenever there isn't, the gas backup or a lower thermostat setpoint takes over. That's great for cost, but *Legionella pneumophila* can proliferate in water that hovers in the 20–45°C range for extended periods. Municipal/plumbing-code guidance is typically to periodically raise stored water to ~60°C for a sustained period to kill it off. This integration automates that check and, when needed, the disinfection cycle itself — without requiring the geyser to run hot all the time.

## Features

- Rolling-window compliance tracking (default 7 days) against a configurable target temperature and hold duration (default 60°C for 32 minutes)
- Automatic cycle start when due (optionally restricted to a time-of-day window, e.g. only run overnight), plus a manual trigger button/service
- A hard failsafe run-time cutoff (default 180 minutes) that disengages the heater and raises an error state if a cycle can't complete
- Configurable strictness for what happens if temperature dips below target mid-cycle: pause-and-resume (default) or reset-to-zero
- Survives Home Assistant restarts safely — the last successful cycle timestamp is persisted, but a restart **never** auto-resumes an in-progress heating cycle
- Native HA events (`geyser_pasteurization_started`, `geyser_pasteurization_completed`, `geyser_pasteurization_failed`) for automations/notifications
- Works with `switch`, `input_boolean`, `climate`, or `water_heater` entities as the heater control
- Optional grid-power gate for battery/inverter setups: cycles only start (and are paused, not cancelled, mid-cycle) while you're on grid power — see [Grid power gate](#grid-power-gate-battery--inverter-setups) below
- Fully configurable via the UI (config flow + options flow) — no YAML required

## Installation

### HACS (custom repository)

1. In HACS, go to **Integrations → ⋮ → Custom repositories**.
2. Add `https://github.com/ChrisPotDev/geyser_pasteurization` as an **Integration**.
3. Install **Geyser Pasteurization**, then restart Home Assistant.

### Manual

1. Copy `custom_components/geyser_pasteurization/` from this repository into your Home Assistant `config/custom_components/` directory, so you end up with `config/custom_components/geyser_pasteurization/...`.
2. Restart Home Assistant.

### Add the integration

**Settings → Devices & Services → Add Integration → "Geyser Pasteurization"**, then follow the config flow.

## Configuration

All configuration is done through the UI. On initial setup you're asked for:

| Field | Description | Default |
|---|---|---|
| Geyser temperature sensor | A `sensor` entity with `device_class: temperature` reporting the geyser's water temperature | — |
| Heater control entity | A `switch`, `input_boolean`, `climate`, or `water_heater` entity that engages the electric element | — |
| Target disinfection temperature | Water must reach/hold this temperature (°C) | 60.0 |
| Required continuous duration | Minutes the temperature must stay at/above target, continuously | 32 |
| Maximum rolling window | Days without a valid cycle before the system is marked "due" | 7 |
| Maximum failsafe run time | Safety cutoff — heater is disengaged and the cycle fails if it runs this long without completing | 180 |
| Allowed run window (optional) | Restricts *automatic* cycle starts to a time-of-day range (e.g. 02:00–05:00). Manual triggers always bypass this. | none (anytime) |
| Strict cycle reset | If a cycle drops below target mid-hold: `off` pauses the timer and resumes when temp recovers; `on` resets the timer to zero | off |
| Grid power sensor (optional) | Any entity reporting your power source. See [Grid power gate](#grid-power-gate-battery--inverter-setups). | none (always allowed) |
| "On grid" state value | The exact state string of the sensor above that means "on grid power" | `on` |

All of these except the two entities can be changed later via **Settings → Devices & Services → Geyser Pasteurization → Configure** (the options flow), without removing and re-adding the integration.

## Grid power gate (battery / inverter setups)

If your geyser sits behind a power distribution module that can switch it between grid and inverter/battery (e.g. to protect battery capacity, with automatic failover to inverter on a grid outage), you don't want a disinfection cycle heating off your battery. Set the **grid power sensor** field to any entity that reflects your current power source — a `binary_sensor`, `switch`, `input_boolean`, or a text/enum `sensor` (e.g. one reporting `"Grid"` / `"Battery"` from a Victron, Deye, Sunsynk, etc. integration) — and set **"On grid" state value** to whatever that entity reports when you're on grid (defaults to `on`, which already matches a plain binary_sensor/switch with no changes needed; for a text sensor you'd set this to e.g. `Grid`). The match is case-insensitive.

If your source is a text/enum sensor and you'd rather not touch the state-value matching, you can instead wrap it in a [template binary_sensor helper](https://www.home-assistant.io/integrations/template/) that's `on` when on grid, and point the grid power sensor field at that helper with the default `on` value — either approach works equally well.

With this configured:

- **Due → Heating** only happens while on grid power (in addition to the allowed run window, if set).
- **Mid-cycle grid loss** (Heating or Pasteurizing) immediately disengages the heater and pauses the cycle — progress toward the required hold duration is preserved, not reset — and it resumes automatically the moment grid power returns, picking up where it left off.
- Time spent paused waiting for grid power does **not** count against the failsafe run-time cutoff; only actual heater-engaged time does.
- The **manual trigger** button/service also respects this gate and refuses to start a cycle while off-grid (the status sensor's `error_message` attribute explains why).
- A `binary_sensor.geyser_on_grid_power` entity is added automatically once a grid sensor is configured, and the status sensor also exposes `on_grid_power` and `paused_reason` attributes for dashboards/automations.

This is handled natively by the integration's own state machine rather than through a separate automation, specifically so that a grid outage mid-cycle pauses and resumes correctly instead of losing progress or needing you to script that logic yourself.

## How it works — the state machine

```
 COMPLIANT ──(window elapsed)──▶ DUE ──(window ok / manual trigger)──▶ HEATING
     ▲                                                                    │
     │                                                          (temp ≥ target)
     │                                                                    ▼
     └──────────────(hold duration reached)────────────── PASTEURIZING
                                                                    │
                                                        (temp < target, non-strict)
                                                                    ▼
                                                                 HEATING
                                                                    │
                                                     (runtime ≥ max failsafe, any state)
                                                                    ▼
                                                                 FAILED (manual reset required)
```

- **Compliant** — a valid cycle completed within the rolling window.
- **Due** — the window has elapsed with no valid cycle. If no allowed-run-window is configured (or the current time is inside it), a cycle starts automatically; otherwise it waits.
- **Heating** — the heater is engaged, temperature rising toward target.
- **Pasteurizing** — temperature is at/above target; the hold-duration timer is counting. If temperature drops below target, the timer either pauses (default) or resets to zero (strict mode), and the state falls back to Heating.
- **Failed** — the heater ran for the configured maximum failsafe time without completing a hold. The heater is disengaged immediately and the state stays Failed until you acknowledge it (Reset or Cancel).

## Entities

Every entity is grouped under a single **Geyser Pasteurization** device.

| Entity | Type | Description |
|---|---|---|
| `sensor.geyser_pasteurization_status` | Sensor (enum) | Current state: `compliant`, `due`, `heating`, `pasteurizing`, `failed` |
| `sensor.geyser_last_pasteurization` | Sensor (timestamp) | When the last successful cycle completed |
| `sensor.geyser_days_since_pasteurization` | Sensor | Days elapsed since the last successful cycle |
| `sensor.geyser_cycle_progress` | Sensor | 0–100% progress of an active hold; attributes include minutes elapsed/remaining |
| `binary_sensor.geyser_pasteurization_overdue` | Binary sensor | `on` when the rolling window has been exceeded |
| `binary_sensor.geyser_pasteurization_active` | Binary sensor | `on` while heating or pasteurizing |
| `binary_sensor.geyser_on_grid_power` | Binary sensor | `on` while on grid power. Only created if a grid power sensor is configured. |
| `button.trigger_pasteurization_cycle` | Button | Immediately starts a cycle, bypassing the allowed run window (but not the grid power gate, if configured) |
| `button.reset_pasteurization_timer` | Button | Marks the system as pasteurized *now* (e.g. you verified disinfection some other way), without running a cycle |
| `button.cancel_pasteurization_cycle` | Button | Safely aborts an in-progress cycle (heater off) without marking it compliant |

## Services

| Service | Description | Fields |
|---|---|---|
| `geyser_pasteurization.manual_pasteurization_trigger` | Immediately starts a disinfection cycle | `device_id` or `entry_id` (optional if you only have one instance configured) |
| `geyser_pasteurization.reset_timer` | Marks the system as pasteurized now, without running a cycle | `device_id` or `entry_id` |
| `geyser_pasteurization.cancel_pasteurization_cycle` | Aborts an in-progress cycle | `device_id` or `entry_id` |

Example:

```yaml
service: geyser_pasteurization.manual_pasteurization_trigger
data:
  device_id: <your device id>
```

## Events

Listen for these in automations to hook up mobile notifications, dashboards, or logbook entries:

| Event | Fired when | Data |
|---|---|---|
| `geyser_pasteurization_started` | A cycle begins heating | `entry_id`, `target_temperature`, `required_duration_minutes` |
| `geyser_pasteurization_completed` | A cycle successfully holds target for the required duration | `entry_id`, `completed_at`, `duration_seconds` |
| `geyser_pasteurization_failed` | The failsafe run-time is exceeded without completing | `entry_id`, `reason`, `failed_at` |

Example automation — notify on failure:

```yaml
automation:
  - alias: Notify on failed pasteurization cycle
    trigger:
      - platform: event
        event_type: geyser_pasteurization_failed
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "Geyser disinfection failed"
          message: "{{ trigger.event.data.reason }}"
```

## Dashboard example

```yaml
type: entities
title: Geyser Pasteurization
entities:
  - entity: sensor.geyser_pasteurization_status
  - entity: sensor.geyser_cycle_progress
  - entity: sensor.geyser_days_since_pasteurization
  - entity: sensor.geyser_last_pasteurization
  - entity: binary_sensor.geyser_pasteurization_overdue
  - entity: button.trigger_pasteurization_cycle
  - entity: button.reset_pasteurization_timer
  - entity: button.cancel_pasteurization_cycle
```

## Safety notes

- The heater is only ever commanded via `turn_on`/`turn_off` on the domain you configured (`switch`, `input_boolean`, `climate`, or `water_heater`). Make sure that entity actually controls the electric element you intend to pasteurize with — this integration has no independent way to verify that.
- The failsafe run-time cutoff is a hard ceiling; if you have a geyser that's very slow to heat, raise it rather than relying on default 180 minutes.
- A Home Assistant restart never resumes an in-progress cycle automatically — after a restart the integration only recomputes whether you're `compliant` or `due` from the last persisted successful-cycle timestamp, and will only start a new cycle through the normal due/allowed-window/manual-trigger logic.
- A `failed` state requires a manual **Reset** or **Cancel** — it will not silently retry.

## Troubleshooting

- **Status stuck on `due`, never starts heating** — check whether an allowed run window is configured and you're outside it; either wait or use the manual trigger button/service.
- **Temperature sensor unavailable/unknown** — the integration logs a warning and pauses timer accumulation (it does not turn the heater off) until the sensor reports a valid numeric value again.
- **Heater entity doesn't respond** — confirm its domain is one of `switch`, `input_boolean`, `climate`, `water_heater`, and that the entity actually accepts `turn_on`/`turn_off`.

## License

[MIT](LICENSE)
