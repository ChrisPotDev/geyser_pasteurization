"""Button platform for the Geyser Pasteurization integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
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
    """Set up Geyser Pasteurization buttons."""
    coordinator: GeyserPasteurizationCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            GeyserTriggerButton(coordinator, entry),
            GeyserResetButton(coordinator, entry),
            GeyserCancelButton(coordinator, entry),
        ]
    )


class _GeyserButtonBase(CoordinatorEntity[GeyserPasteurizationCoordinator], ButtonEntity):
    """Base class providing shared device info."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GeyserPasteurizationCoordinator,
        entry: ConfigEntry,
        description: ButtonEntityDescription,
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


class GeyserTriggerButton(_GeyserButtonBase):
    """Immediately starts a disinfection cycle."""

    def __init__(self, coordinator: GeyserPasteurizationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(
            coordinator,
            entry,
            ButtonEntityDescription(
                key="trigger_pasteurization_cycle",
                translation_key="trigger_pasteurization_cycle",
                icon="mdi:water-boiler",
            ),
        )

    async def async_press(self) -> None:
        await self.coordinator.async_manual_trigger()


class GeyserResetButton(_GeyserButtonBase):
    """Manually marks the system as pasteurized."""

    def __init__(self, coordinator: GeyserPasteurizationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(
            coordinator,
            entry,
            ButtonEntityDescription(
                key="reset_pasteurization_timer",
                translation_key="reset_pasteurization_timer",
                icon="mdi:timer-refresh-outline",
            ),
        )

    async def async_press(self) -> None:
        await self.coordinator.async_reset_timer()


class GeyserCancelButton(_GeyserButtonBase):
    """Safely aborts an in-progress disinfection cycle."""

    def __init__(self, coordinator: GeyserPasteurizationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(
            coordinator,
            entry,
            ButtonEntityDescription(
                key="cancel_pasteurization_cycle",
                translation_key="cancel_pasteurization_cycle",
                icon="mdi:stop-circle-outline",
            ),
        )

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data.state in ACTIVE_STATES

    async def async_press(self) -> None:
        await self.coordinator.async_cancel_cycle()
