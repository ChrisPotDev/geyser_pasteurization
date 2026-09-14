# Geyser Pasteurization

A Home Assistant custom integration that manages Legionella pasteurization/disinfection cycles for a hybrid hot water (geyser) system — designed for setups where solar PV diversion causes irregular, sometimes-too-low water temperatures that let bacteria proliferate.

It watches a temperature sensor over a rolling window, and if the water hasn't reliably reached and held a safe disinfection temperature, it automatically (or manually) engages a heater entity, holds it at temperature for a required duration, and logs the result — with a hard failsafe timeout so it can never run away.

## Why this exists

Hybrid geysers with solar diversion heat opportunistically: whenever there's excess PV, the electric element kicks in, and whenever there isn't, the gas backup or a lower thermostat setpoint takes over. That's great for cost, but *Legionella pneumophila* can proliferate in water that hovers in the 20–45°C range for extended periods. Municipal/plumbing-code guidance is typically to periodically raise stored water to ~60°C for a sustained period to kill it off. This integration automates that check and, when needed, the disinfection cycle itself — without requiring the geyser to run hot all the time.

## Features

- Rolling-window compliance tracking (default 7 days) against a configurable target temperature and hold duration (default 60°C for 32 minutes)
- Recognizes disinfection that happens on its own (e.g. solar diversion reaching target) and won't redundantly run its own active cycle on top of it — see [Passive / solar-driven pasteurization](#passive--solar-driven-pasteurization) below
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

## Passive / solar-driven pasteurization

Hold-time toward the required duration is tracked purely from the temperature sensor reading — not from whether *this integration's* heater is currently switched on. That means:

- **If the tank is already at/above target when a cycle becomes due, the integration does not engage its own heater on top of it.** It just watches the sensor and lets the existing heat (from solar diversion, or anything else) accumulate hold-time on its own. Status goes straight to `pasteurizing` without ever passing through `heating`, and no `geyser_pasteurization_started` event fires — only `geyser_pasteurization_completed` once the hold duration is satisfied, with a `heater_engaged: false` attribute so you can tell it happened for free.
- **Once the tank crosses target, tracking continues even after whatever heated it switches off.** If solar's own controller shuts the element off the moment it reaches target, the water stays hot for a while on thermal mass alone — the integration keeps counting based on the sensor reading until either the hold duration is satisfied, or the temperature actually drops back below target.
- **If a passive hold doesn't quite finish before temperature drops** (e.g. the sun goes behind a cloud a few minutes short of the full duration), and the cycle is still due, the integration tops it up with its own heater rather than starting over — the partial hold-time already banked is preserved, not discarded (unless you've enabled **strict cycle reset**, in which case any drop below target always zeroes the timer, passive or not).
- **This applies independently of the grid power gate.** Losing grid power only stops the integration engaging its *own* heater; it doesn't stop it from recognizing an already-hot tank, since that heat didn't come from the battery in the first place.
- **The integration will never turn off a heater it did not itself turn on.** Internally it only ever calls `turn_off` on the heater entity when it's the one that called `turn_on` for the current hold — automatically (grid loss, cycle completion, failsafe) or via the Reset/Cancel button/service. A passive/solar-driven hold is only ever *watched*, never interrupted.

In short: an active cycle (heater engaged by this integration) only ever happens for the portion of the required duration that ambient/solar heating hasn't already covered.

## How it works — the state machine

```
 COMPLIANT ──(window elapsed)──▶ DUE ──(temp < target: window ok / manual trigger)──▶ HEATING
     ▲  ▲                          │  │                                                  │
     │  │                          │  └──(temp ≥ target, any time)──▶ PASTEURIZING ◀──────┘
     │  │                          │                                       │      (temp ≥ target)
     │  └──(temp ≥ target, any time, no window needed)────────────────────►│
     │                                                                     │
     └──────────────────────(hold duration reached)──────────────────────┘
                                                                            │
                                                            (temp < target, non-strict: keep banked time)
                                                                            ▼
                                                                         HEATING / DUE
                                                                            │
                                                         (heater-engaged runtime ≥ max failsafe)
                                                                            ▼
                                                                         FAILED (manual reset required)
```

- **Compliant** — a valid hold completed within the rolling window (whether driven by the integration's own heater, passively, or a mix of both).
- **Due** — the window has elapsed with no valid hold recorded, and the tank is currently below target. If on grid power and (no allowed-run-window is configured, or the current time is inside it), the integration's own heater engages; otherwise it waits — including waiting on ambient/solar heating to bring it up on its own.
- **Heating** — *this integration's* heater is engaged, temperature rising toward target.
- **Pasteurizing** — temperature is at/above target right now, however that happened; the hold-duration timer is counting. If temperature drops below target before completion, the timer either pauses (default) or resets to zero (strict mode), falling back to `heating` (if the integration's heater is engaged) or `due` (if not, e.g. it was a passive hold).
- **Failed** — *the integration's own heater* ran for the configured maximum failsafe time without completing a hold (time spent passively at temperature, or paused for grid power, never counts toward this). The heater is disengaged immediately and the state stays Failed until you acknowledge it (Reset or Cancel).

## Entities

Every entity is grouped under a single **Geyser Pasteurization** device.

| Entity | Type | Description |
|---|---|---|
| `sensor.geyser_pasteurization_status` | Sensor (enum) | Current state: `compliant`, `due`, `heating`, `pasteurizing`, `failed`. `pasteurizing` can be reached without `heating` if the tank is already hot passively (e.g. from solar) — see [Passive / solar-driven pasteurization](#passive--solar-driven-pasteurization). |
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
| `geyser_pasteurization_started` | The integration engages its own heater (never fires for a purely passive/solar hold) | `entry_id`, `target_temperature`, `required_duration_minutes`, `banked_hold_seconds` (any passive hold-time already accumulated before engaging) |
| `geyser_pasteurization_completed` | A hold at/above target completes for the required duration | `entry_id`, `completed_at`, `duration_seconds`, `heater_engaged` (`false` if fully passive/solar-driven) |
| `geyser_pasteurization_failed` | The integration's own heater-engaged runtime exceeds the failsafe without completing | `entry_id`, `reason`, `failed_at` |

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

- **Status stuck on `due`, never starts heating** — check whether an allowed run window or grid power gate is configured and currently blocking it; either wait, adjust the window, or use the manual trigger button/service. Also check whether the tank is already at/above target — if so, this is expected: it's waiting on the passive hold to finish rather than engaging its own heater (see [Passive / solar-driven pasteurization](#passive--solar-driven-pasteurization)).
- **Temperature sensor unavailable/unknown** — the integration logs a warning and pauses timer accumulation (it does not turn the heater off) until the sensor reports a valid numeric value again.
- **Heater entity doesn't respond** — confirm its domain is one of `switch`, `input_boolean`, `climate`, `water_heater`, and that the entity actually accepts `turn_on`/`turn_off`.

## License

[MIT](LICENSE)
