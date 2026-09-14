"""DataUpdateCoordinator for the Geyser Pasteurization integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time as dt_time, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    ACTIVE_STATES,
    CONF_ALLOWED_END,
    CONF_ALLOWED_START,
    CONF_GRID_ON_STATE,
    CONF_GRID_SENSOR,
    CONF_HEATER_ENTITY,
    CONF_MAX_RUNTIME,
    CONF_REQUIRED_DURATION,
    CONF_ROLLING_WINDOW,
    CONF_STRICT_RESET,
    CONF_TARGET_TEMP,
    CONF_TEMP_SENSOR,
    DEFAULT_GRID_ON_STATE,
    DEFAULT_MAX_RUNTIME_MINUTES,
    DEFAULT_REQUIRED_DURATION_MINUTES,
    DEFAULT_ROLLING_WINDOW_DAYS,
    DEFAULT_STRICT_RESET,
    DEFAULT_TARGET_TEMP,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
    DOMAIN,
    EVENT_COMPLETED,
    EVENT_FAILED,
    EVENT_STARTED,
    HEATER_DOMAINS,
    STATE_COMPLIANT,
    STATE_DUE,
    STATE_FAILED,
    STATE_HEATING,
    STATE_PASTEURIZING,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class GeyserPasteurizationData:
    """Snapshot of coordinator state consumed by entities."""

    state: str
    last_pasteurization: datetime | None
    days_since: float | None
    overdue: bool
    current_temperature: float | None
    target_temperature: float
    cycle_elapsed_seconds: float
    cycle_runtime_seconds: float
    cycle_progress_percent: float
    required_duration_seconds: float
    rolling_window_days: int
    max_runtime_minutes: int
    minutes_remaining: float
    error_message: str | None
    on_grid_power: bool
    paused_reason: str | None


class GeyserPasteurizationCoordinator(DataUpdateCoordinator[GeyserPasteurizationData]):
    """Coordinates temperature monitoring and the pasteurization state machine."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL_SECONDS),
        )
        self.entry = entry
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}_{entry.entry_id}"
        )

        self._state: str = STATE_DUE
        self._last_pasteurization: datetime | None = None
        self._cycle_elapsed_seconds: float = 0.0
        self._cycle_runtime_seconds: float = 0.0
        self._last_tick: datetime | None = None
        self._error_message: str | None = None
        self._heater_on: bool = False
        self._temp_unavailable_logged: bool = False
        self._grid_unavailable_logged: bool = False
        self._grid_blocked: bool = False
        self._unsub_temp_listener: Any = None
        self._unsub_grid_listener: Any = None

    # ------------------------------------------------------------------
    # Options / configuration helpers
    # ------------------------------------------------------------------
    def _option(self, key: str, default: Any) -> Any:
        return self.entry.options.get(key, self.entry.data.get(key, default))

    @property
    def temp_sensor_entity_id(self) -> str:
        return self.entry.data[CONF_TEMP_SENSOR]

    @property
    def heater_entity_id(self) -> str:
        return self.entry.data[CONF_HEATER_ENTITY]

    @property
    def target_temperature(self) -> float:
        return float(self._option(CONF_TARGET_TEMP, DEFAULT_TARGET_TEMP))

    @property
    def required_duration_minutes(self) -> int:
        return int(self._option(CONF_REQUIRED_DURATION, DEFAULT_REQUIRED_DURATION_MINUTES))

    @property
    def required_duration_seconds(self) -> float:
        return self.required_duration_minutes * 60.0

    @property
    def rolling_window_days(self) -> int:
        return int(self._option(CONF_ROLLING_WINDOW, DEFAULT_ROLLING_WINDOW_DAYS))

    @property
    def max_runtime_minutes(self) -> int:
        return int(self._option(CONF_MAX_RUNTIME, DEFAULT_MAX_RUNTIME_MINUTES))

    @property
    def max_runtime_seconds(self) -> float:
        return self.max_runtime_minutes * 60.0

    @property
    def strict_reset(self) -> bool:
        return bool(self._option(CONF_STRICT_RESET, DEFAULT_STRICT_RESET))

    @property
    def allowed_start_time(self) -> dt_time | None:
        value = self._option(CONF_ALLOWED_START, None)
        if not value:
            return None
        return dt_util.parse_time(value)

    @property
    def allowed_end_time(self) -> dt_time | None:
        value = self._option(CONF_ALLOWED_END, None)
        if not value:
            return None
        return dt_util.parse_time(value)

    @property
    def grid_sensor_entity_id(self) -> str | None:
        return self._option(CONF_GRID_SENSOR, None) or None

    @property
    def grid_on_state(self) -> str:
        return str(self._option(CONF_GRID_ON_STATE, DEFAULT_GRID_ON_STATE) or DEFAULT_GRID_ON_STATE)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def async_initialize(self) -> None:
        """Load persisted state and start listening for sensor updates."""
        stored = await self._store.async_load()
        if stored and stored.get("last_pasteurization"):
            self._last_pasteurization = dt_util.parse_datetime(stored["last_pasteurization"])
        else:
            self._last_pasteurization = None

        # A restart must never resume an in-progress heating cycle. The
        # heater is left exactly as it was found; only bookkeeping state
        # is recomputed from the persisted last-successful-cycle timestamp.
        self._state = self._compute_idle_state(dt_util.utcnow())

        self._unsub_temp_listener = async_track_state_change_event(
            self.hass, [self.temp_sensor_entity_id], self._async_watched_entity_changed
        )
        if self.grid_sensor_entity_id:
            self._unsub_grid_listener = async_track_state_change_event(
                self.hass, [self.grid_sensor_entity_id], self._async_watched_entity_changed
            )

    async def async_shutdown_listeners(self) -> None:
        if self._unsub_temp_listener is not None:
            self._unsub_temp_listener()
            self._unsub_temp_listener = None
        if self._unsub_grid_listener is not None:
            self._unsub_grid_listener()
            self._unsub_grid_listener = None

    @callback
    def _async_watched_entity_changed(self, event: Event[EventStateChangedData]) -> None:
        self.hass.async_create_task(self.async_request_refresh())

    def _compute_idle_state(self, now: datetime) -> str:
        if self._is_overdue(now):
            return STATE_DUE
        return STATE_COMPLIANT

    def _is_overdue(self, now: datetime) -> bool:
        if self._last_pasteurization is None:
            return True
        days = (now - self._last_pasteurization).total_seconds() / 86400
        return days >= self.rolling_window_days

    # ------------------------------------------------------------------
    # Main update loop
    # ------------------------------------------------------------------
    async def _async_update_data(self) -> GeyserPasteurizationData:
        now = dt_util.utcnow()
        temperature = self._read_temperature()
        on_grid = self._is_on_grid()

        await self._async_process_state(now, temperature, on_grid)

        days_since: float | None = None
        if self._last_pasteurization is not None:
            days_since = (now - self._last_pasteurization).total_seconds() / 86400

        progress = 0.0
        if self.required_duration_seconds > 0:
            progress = min(
                100.0, (self._cycle_elapsed_seconds / self.required_duration_seconds) * 100
            )

        minutes_remaining = max(
            0.0, (self.required_duration_seconds - self._cycle_elapsed_seconds) / 60
        )

        return GeyserPasteurizationData(
            state=self._state,
            last_pasteurization=self._last_pasteurization,
            days_since=days_since,
            overdue=self._is_overdue(now),
            current_temperature=temperature,
            target_temperature=self.target_temperature,
            cycle_elapsed_seconds=self._cycle_elapsed_seconds,
            cycle_runtime_seconds=self._cycle_runtime_seconds,
            cycle_progress_percent=progress,
            required_duration_seconds=self.required_duration_seconds,
            rolling_window_days=self.rolling_window_days,
            max_runtime_minutes=self.max_runtime_minutes,
            minutes_remaining=minutes_remaining,
            error_message=self._error_message,
            on_grid_power=on_grid,
            paused_reason="Waiting for grid power" if self._grid_blocked else None,
        )

    def _is_on_grid(self) -> bool:
        entity_id = self.grid_sensor_entity_id
        if not entity_id:
            return True
        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            if not self._grid_unavailable_logged:
                _LOGGER.warning(
                    "Grid power sensor %s is unavailable or unknown; "
                    "treating as not-on-grid as a safety precaution",
                    entity_id,
                )
                self._grid_unavailable_logged = True
            return False
        self._grid_unavailable_logged = False
        return state.state.strip().casefold() == self.grid_on_state.strip().casefold()

    def _read_temperature(self) -> float | None:
        state = self.hass.states.get(self.temp_sensor_entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            if not self._temp_unavailable_logged:
                _LOGGER.warning(
                    "Temperature sensor %s is unavailable or unknown",
                    self.temp_sensor_entity_id,
                )
                self._temp_unavailable_logged = True
            return None
        try:
            value = float(state.state)
        except (TypeError, ValueError):
            if not self._temp_unavailable_logged:
                _LOGGER.error(
                    "Temperature sensor %s reported a non-numeric state: %s",
                    self.temp_sensor_entity_id,
                    state.state,
                )
                self._temp_unavailable_logged = True
            return None
        self._temp_unavailable_logged = False
        return value

    def _within_allowed_window(self, now: datetime) -> bool:
        start = self.allowed_start_time
        end = self.allowed_end_time
        if start is None or end is None:
            return True
        now_local = dt_util.as_local(now).time()
        if start <= end:
            return start <= now_local <= end
        # Window crosses midnight.
        return now_local >= start or now_local <= end

    async def _async_process_state(
        self, now: datetime, temperature: float | None, on_grid: bool
    ) -> None:
        """Advance the state machine.

        Hold-time toward the required duration is tracked purely from the
        temperature reading, regardless of whether *we* engaged the heater
        or it got there some other way (e.g. solar diversion). This means a
        cycle can complete — or be well under way — without the integration
        ever having turned the heater on, and it will not redundantly start
        its own active cycle while the tank is already at/above target.
        """
        elapsed = 0.0
        if self._last_tick is not None:
            elapsed = max(0.0, (now - self._last_tick).total_seconds())
        self._last_tick = now

        if self._state == STATE_FAILED:
            return  # Remains until manually acknowledged/reset.

        # Keep our own heater in sync with grid availability. This is
        # independent of the hold timer: losing grid stops us actively
        # driving the element, but a tank that's already hot (e.g. from
        # solar) keeps accumulating hold-time regardless.
        if self._heater_on and not on_grid:
            await self._async_pause_for_grid()
        elif self._grid_blocked and on_grid:
            self._grid_blocked = False

        at_target = temperature is not None and temperature >= self.target_temperature

        if at_target:
            self._cycle_elapsed_seconds += elapsed
            if self._heater_on:
                self._cycle_runtime_seconds += elapsed
                if await self._async_check_failsafe(now):
                    return
            if self._cycle_elapsed_seconds >= self.required_duration_seconds:
                await self._async_complete_cycle(now)
                return
            if self._state != STATE_PASTEURIZING:
                self._state = STATE_PASTEURIZING
                _LOGGER.info(
                    "Geyser at/above target temperature (%.1f°C); pasteurization timer running%s",
                    temperature,
                    "" if self._heater_on else " (passively, heater not engaged by this integration)",
                )
            return

        if temperature is None:
            # Cannot confirm temperature; hold position without
            # accumulating or discarding hold progress.
            if self._heater_on:
                self._cycle_runtime_seconds += elapsed
                await self._async_check_failsafe(now)
            return

        # Temperature is confirmed below target. Only log/react to the
        # *transition* (state was still Pasteurizing as of the last tick);
        # otherwise this would log on every poll while parked below target.
        if self._state == STATE_PASTEURIZING and self._cycle_elapsed_seconds > 0:
            if self.strict_reset:
                self._cycle_elapsed_seconds = 0.0
                _LOGGER.info(
                    "Temperature dropped below target; strict mode reset the cycle timer"
                )
            else:
                _LOGGER.info(
                    "Temperature dropped below target; cycle timer paused at %.1f minutes",
                    self._cycle_elapsed_seconds / 60,
                )

        if self._heater_on:
            self._cycle_runtime_seconds += elapsed
            if await self._async_check_failsafe(now):
                return
            self._state = STATE_HEATING
            return

        if self._is_overdue(now) and on_grid and self._within_allowed_window(now):
            await self._async_start_cycle(now)
            return

        self._state = STATE_DUE if self._is_overdue(now) else STATE_COMPLIANT

    async def _async_pause_for_grid(self) -> None:
        if not self._grid_blocked:
            _LOGGER.info(
                "Grid power unavailable; pausing pasteurization cycle and disengaging heater"
            )
        self._grid_blocked = True
        await self._async_set_heater(False)

    async def _async_check_failsafe(self, now: datetime) -> bool:
        if self._cycle_runtime_seconds >= self.max_runtime_seconds:
            await self._async_fail_cycle(
                now,
                (
                    f"Heater ran for the maximum allowed {self.max_runtime_minutes} minutes "
                    "without completing a full pasteurization cycle"
                ),
            )
            return True
        return False

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------
    async def _async_start_cycle(self, now: datetime) -> None:
        # Deliberately does not reset cycle_elapsed_seconds: any hold-time
        # already banked (e.g. from a prior solar-driven excursion that
        # didn't quite finish) still counts toward this cycle. Only the
        # failsafe runtime clock resets, since that tracks a fresh attempt
        # at actively driving the heater.
        self._state = STATE_HEATING
        self._cycle_runtime_seconds = 0.0
        self._error_message = None
        self._grid_blocked = False
        self._last_tick = now
        await self._async_set_heater(True)
        self.hass.bus.async_fire(
            EVENT_STARTED,
            {
                "entry_id": self.entry.entry_id,
                "target_temperature": self.target_temperature,
                "required_duration_minutes": self.required_duration_minutes,
                "banked_hold_seconds": self._cycle_elapsed_seconds,
            },
        )
        if self._cycle_elapsed_seconds > 0:
            _LOGGER.info(
                "Starting geyser pasteurization cycle (%.1f minutes of hold time already banked)",
                self._cycle_elapsed_seconds / 60,
            )
        else:
            _LOGGER.info("Starting geyser pasteurization cycle")

    async def _async_complete_cycle(self, now: datetime) -> None:
        self._state = STATE_COMPLIANT
        self._last_pasteurization = now
        duration_seconds = self._cycle_elapsed_seconds
        heater_engaged = self._heater_on
        if heater_engaged:
            await self._async_set_heater(False)
        await self._async_save_store()
        self.hass.bus.async_fire(
            EVENT_COMPLETED,
            {
                "entry_id": self.entry.entry_id,
                "completed_at": now.isoformat(),
                "duration_seconds": duration_seconds,
                "heater_engaged": heater_engaged,
            },
        )
        if heater_engaged:
            _LOGGER.info("Geyser pasteurization cycle completed successfully")
        else:
            _LOGGER.info(
                "Geyser reached and held target temperature passively (e.g. via solar); "
                "marking pasteurization compliant without engaging the heater"
            )
        self._cycle_elapsed_seconds = 0.0
        self._cycle_runtime_seconds = 0.0

    async def _async_fail_cycle(self, now: datetime, reason: str) -> None:
        self._state = STATE_FAILED
        self._error_message = reason
        await self._async_set_heater(False)
        self.hass.bus.async_fire(
            EVENT_FAILED,
            {
                "entry_id": self.entry.entry_id,
                "reason": reason,
                "failed_at": now.isoformat(),
            },
        )
        _LOGGER.error("Geyser pasteurization cycle failed: %s", reason)

    async def _async_set_heater(self, turn_on: bool) -> None:
        entity_id = self.heater_entity_id
        domain = entity_id.split(".", 1)[0]
        if domain not in HEATER_DOMAINS:
            message = f"Unsupported heater entity domain: {domain}"
            _LOGGER.error("Unsupported heater entity domain: %s", domain)
            self._error_message = message
            return

        service = "turn_on" if turn_on else "turn_off"
        try:
            await self.hass.services.async_call(
                domain, service, {"entity_id": entity_id}, blocking=True
            )
        except HomeAssistantError as err:
            action = "engage" if turn_on else "disengage"
            message = f"Failed to {action} heater {entity_id}: {err}"
            _LOGGER.error("Failed to %s heater %s: %s", action, entity_id, err)
            self._error_message = message
            return
        self._heater_on = turn_on

    async def _async_save_store(self) -> None:
        await self._store.async_save(
            {
                "last_pasteurization": (
                    self._last_pasteurization.isoformat() if self._last_pasteurization else None
                )
            }
        )

    # ------------------------------------------------------------------
    # Public actions (services / buttons)
    # ------------------------------------------------------------------
    async def async_manual_trigger(self) -> None:
        """Immediately start a disinfection cycle, bypassing the allowed window."""
        if self._state in ACTIVE_STATES:
            _LOGGER.warning("Pasteurization cycle already in progress; ignoring manual trigger")
            return
        if not self._is_on_grid():
            _LOGGER.warning(
                "Manual pasteurization trigger ignored: not currently on grid power"
            )
            self._error_message = "Manual trigger blocked: not currently on grid power"
            await self.async_request_refresh()
            return
        now = dt_util.utcnow()
        await self._async_start_cycle(now)
        await self.async_request_refresh()

    async def async_reset_timer(self) -> None:
        """Manually mark the system as pasteurized (e.g. verified by other means)."""
        now = dt_util.utcnow()
        if self._heater_on:
            # Only disengage the heater if this integration is the one
            # driving it — never touch it if the current hold is passive
            # (e.g. solar-driven), since we never turned it on.
            await self._async_set_heater(False)
        self._state = STATE_COMPLIANT
        self._last_pasteurization = now
        self._cycle_elapsed_seconds = 0.0
        self._cycle_runtime_seconds = 0.0
        self._error_message = None
        self._grid_blocked = False
        await self._async_save_store()
        await self.async_request_refresh()

    async def async_cancel_cycle(self) -> None:
        """Abort an in-progress cycle without marking the system compliant."""
        if self._state not in ACTIVE_STATES:
            return
        if self._heater_on:
            # As in async_reset_timer: only disengage a heater this
            # integration itself engaged, never a passive/solar-driven hold.
            await self._async_set_heater(False)
        self._state = STATE_DUE
        self._cycle_elapsed_seconds = 0.0
        self._cycle_runtime_seconds = 0.0
        self._grid_blocked = False
        await self.async_request_refresh()
