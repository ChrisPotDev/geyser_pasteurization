"""Binary sensor platform for the Geyser Pasteurization integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ACTIVE_STATES, DOMAIN, MANUFACTURER, MODEL
from .coordinator import GeyserPasteurizationCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Geyser Pasteurization binary sensors."""
    coordinator: GeyserPasteurizationCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[_GeyserBinarySensorBase] = [
        GeyserOverdueBinarySensor(coordinator, entry),
        GeyserActiveBinarySensor(coordinator, entry),
    ]
    if coordinator.grid_sensor_entity_id:
        entities.append(GeyserGridPowerBinarySensor(coordinator, entry))

    async_add_entities(entities)


class _GeyserBinarySensorBase(
    CoordinatorEntity[GeyserPasteurizationCoordinator], BinarySensorEntity
):
    """Base class providing shared device info."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GeyserPasteurizationCoordinator,
        entry: ConfigEntry,
        description: BinarySensorEntityDescription,
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


class GeyserOverdueBinarySensor(_GeyserBinarySensorBase):
    """On when the rolling compliance window has been exceeded."""

    def __init__(self, coordinator: GeyserPasteurizationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(
            coordinator,
            entry,
            BinarySensorEntityDescription(
                key="pasteurization_overdue",
                translation_key="pasteurization_overdue",
                device_class=BinarySensorDeviceClass.PROBLEM,
            ),
        )

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.overdue


class GeyserActiveBinarySensor(_GeyserBinarySensorBase):
    """On while a disinfection cycle is heating or pasteurizing."""

    def __init__(self, coordinator: GeyserPasteurizationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(
            coordinator,
            entry,
            BinarySensorEntityDescription(
                key="pasteurization_active",
                translation_key="pasteurization_active",
                device_class=BinarySensorDeviceClass.RUNNING,
            ),
        )

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.state in ACTIVE_STATES


class GeyserGridPowerBinarySensor(_GeyserBinarySensorBase):
    """On while the configured grid power sensor reports on-grid power."""

    def __init__(self, coordinator: GeyserPasteurizationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(
            coordinator,
            entry,
            BinarySensorEntityDescription(
                key="on_grid_power",
                translation_key="on_grid_power",
                device_class=BinarySensorDeviceClass.POWER,
            ),
        )

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.on_grid_power
