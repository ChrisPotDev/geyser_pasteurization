"""Sensor platform for the Geyser Pasteurization integration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_CYCLE_RUNTIME_MINUTES,
    ATTR_ERROR_MESSAGE,
    ATTR_MAX_RUNTIME_MINUTES,
    ATTR_MINUTES_REMAINING,
    ATTR_REQUIRED_DURATION_MINUTES,
    ATTR_ROLLING_WINDOW_DAYS,
    ATTR_TARGET_TEMPERATURE,
    DOMAIN,
    MANUFACTURER,
    MODEL,
    STATUS_STATES,
)
from .coordinator import GeyserPasteurizationCoordinator, GeyserPasteurizationData


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Geyser Pasteurization sensors."""
    coordinator: GeyserPasteurizationCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            GeyserStatusSensor(coordinator, entry),
            GeyserLastPasteurizationSensor(coordinator, entry),
            GeyserDaysSinceSensor(coordinator, entry),
            GeyserCycleProgressSensor(coordinator, entry),
        ]
    )


class _GeyserSensorBase(CoordinatorEntity[GeyserPasteurizationCoordinator], SensorEntity):
    """Base class providing shared device info."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GeyserPasteurizationCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Geyser Pasteurization",
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def _data(self) -> GeyserPasteurizationData:
        return self.coordinator.data


class GeyserStatusSensor(_GeyserSensorBase):
    """Represents the current disinfection cycle state."""

    def __init__(self, coordinator: GeyserPasteurizationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(
            coordinator,
            entry,
            SensorEntityDescription(
                key="status",
                translation_key="status",
                device_class=SensorDeviceClass.ENUM,
                options=STATUS_STATES,
            ),
        )

    @property
    def native_value(self) -> str:
        return self._data.state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._data
        return {
            ATTR_CURRENT_TEMPERATURE: data.current_temperature,
            ATTR_TARGET_TEMPERATURE: data.target_temperature,
            ATTR_REQUIRED_DURATION_MINUTES: data.required_duration_seconds / 60,
            ATTR_ROLLING_WINDOW_DAYS: data.rolling_window_days,
            ATTR_MAX_RUNTIME_MINUTES: data.max_runtime_minutes,
            ATTR_CYCLE_RUNTIME_MINUTES: round(data.cycle_runtime_seconds / 60, 2),
            ATTR_ERROR_MESSAGE: data.error_message,
        }


class GeyserLastPasteurizationSensor(_GeyserSensorBase):
    """Represents the timestamp of the last successful cycle."""

    def __init__(self, coordinator: GeyserPasteurizationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(
            coordinator,
            entry,
            SensorEntityDescription(
                key="last_pasteurization",
                translation_key="last_pasteurization",
                device_class=SensorDeviceClass.TIMESTAMP,
            ),
        )

    @property
    def native_value(self) -> datetime | None:
        return self._data.last_pasteurization


class GeyserDaysSinceSensor(_GeyserSensorBase):
    """Represents days elapsed since the last successful cycle."""

    def __init__(self, coordinator: GeyserPasteurizationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(
            coordinator,
            entry,
            SensorEntityDescription(
                key="days_since_pasteurization",
                translation_key="days_since_pasteurization",
                native_unit_of_measurement=UnitOfTime.DAYS,
                state_class=SensorStateClass.MEASUREMENT,
                suggested_display_precision=2,
            ),
        )

    @property
    def native_value(self) -> float | None:
        if self._data.days_since is None:
            return None
        return round(self._data.days_since, 2)


class GeyserCycleProgressSensor(_GeyserSensorBase):
    """Represents the progress of an active disinfection cycle."""

    def __init__(self, coordinator: GeyserPasteurizationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(
            coordinator,
            entry,
            SensorEntityDescription(
                key="cycle_progress",
                translation_key="cycle_progress",
                native_unit_of_measurement=PERCENTAGE,
                state_class=SensorStateClass.MEASUREMENT,
                suggested_display_precision=0,
            ),
        )

    @property
    def native_value(self) -> float:
        return round(self._data.cycle_progress_percent, 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._data
        return {
            ATTR_CYCLE_RUNTIME_MINUTES: round(data.cycle_elapsed_seconds / 60, 2),
            ATTR_MINUTES_REMAINING: round(data.minutes_remaining, 2),
            ATTR_REQUIRED_DURATION_MINUTES: data.required_duration_seconds / 60,
        }
