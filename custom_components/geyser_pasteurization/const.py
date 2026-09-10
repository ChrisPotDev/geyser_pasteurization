"""Constants for the Geyser Pasteurization integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "geyser_pasteurization"
PLATFORMS: Final = ["sensor", "binary_sensor", "button"]

MANUFACTURER: Final = "Custom Components"
MODEL: Final = "Legionella Pasteurization Controller"

# --- Configuration keys ---------------------------------------------------
CONF_TEMP_SENSOR: Final = "temperature_sensor"
CONF_HEATER_ENTITY: Final = "heater_entity"
CONF_TARGET_TEMP: Final = "target_temperature"
CONF_REQUIRED_DURATION: Final = "required_duration_minutes"
CONF_ROLLING_WINDOW: Final = "rolling_window_days"
CONF_MAX_RUNTIME: Final = "max_runtime_minutes"
CONF_ALLOWED_START: Final = "allowed_start_time"
CONF_ALLOWED_END: Final = "allowed_end_time"
CONF_STRICT_RESET: Final = "strict_reset"

# --- Defaults ---------------------------------------------------------------
DEFAULT_TARGET_TEMP: Final = 60.0
DEFAULT_REQUIRED_DURATION_MINUTES: Final = 32
DEFAULT_ROLLING_WINDOW_DAYS: Final = 7
DEFAULT_MAX_RUNTIME_MINUTES: Final = 180
DEFAULT_STRICT_RESET: Final = False
DEFAULT_UPDATE_INTERVAL_SECONDS: Final = 30

MIN_TARGET_TEMP: Final = 40.0
MAX_TARGET_TEMP: Final = 80.0
MIN_REQUIRED_DURATION_MINUTES: Final = 1
MAX_REQUIRED_DURATION_MINUTES: Final = 180
MIN_ROLLING_WINDOW_DAYS: Final = 1
MAX_ROLLING_WINDOW_DAYS: Final = 30
MIN_MAX_RUNTIME_MINUTES: Final = 10
MAX_MAX_RUNTIME_MINUTES: Final = 480

HEATER_DOMAINS: Final = ("switch", "input_boolean", "climate", "water_heater")

# --- States -------------------------------------------------------------
STATE_COMPLIANT: Final = "compliant"
STATE_DUE: Final = "due"
STATE_HEATING: Final = "heating"
STATE_PASTEURIZING: Final = "pasteurizing"
STATE_FAILED: Final = "failed"

STATUS_STATES: Final = [
    STATE_COMPLIANT,
    STATE_DUE,
    STATE_HEATING,
    STATE_PASTEURIZING,
    STATE_FAILED,
]

ACTIVE_STATES: Final = (STATE_HEATING, STATE_PASTEURIZING)

# --- Events ---------------------------------------------------------------
EVENT_STARTED: Final = "geyser_pasteurization_started"
EVENT_COMPLETED: Final = "geyser_pasteurization_completed"
EVENT_FAILED: Final = "geyser_pasteurization_failed"

# --- Services ---------------------------------------------------------------
SERVICE_MANUAL_TRIGGER: Final = "manual_pasteurization_trigger"
SERVICE_RESET_TIMER: Final = "reset_timer"
SERVICE_CANCEL_CYCLE: Final = "cancel_pasteurization_cycle"

ATTR_ENTRY_ID: Final = "entry_id"
ATTR_DEVICE_ID: Final = "device_id"

# --- Storage ---------------------------------------------------------------
STORAGE_VERSION: Final = 1
STORAGE_KEY_PREFIX: Final = DOMAIN

# --- Extra state attributes -------------------------------------------------
ATTR_CURRENT_TEMPERATURE: Final = "current_temperature"
ATTR_TARGET_TEMPERATURE: Final = "target_temperature"
ATTR_CYCLE_ELAPSED_SECONDS: Final = "cycle_elapsed_seconds"
ATTR_CYCLE_ELAPSED_MINUTES: Final = "cycle_elapsed_minutes"
ATTR_CYCLE_RUNTIME_SECONDS: Final = "cycle_runtime_seconds"
ATTR_CYCLE_RUNTIME_MINUTES: Final = "cycle_runtime_minutes"
ATTR_REQUIRED_DURATION_MINUTES: Final = "required_duration_minutes"
ATTR_ROLLING_WINDOW_DAYS: Final = "rolling_window_days"
ATTR_MAX_RUNTIME_MINUTES: Final = "max_runtime_minutes"
ATTR_ERROR_MESSAGE: Final = "error_message"
ATTR_LAST_PASTEURIZATION: Final = "last_pasteurization"
ATTR_MINUTES_REMAINING: Final = "minutes_remaining"
