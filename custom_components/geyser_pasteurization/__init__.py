"""The Geyser Pasteurization integration."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import (
    ATTR_DEVICE_ID,
    ATTR_ENTRY_ID,
    DOMAIN,
    SERVICE_CANCEL_CYCLE,
    SERVICE_MANUAL_TRIGGER,
    SERVICE_RESET_TIMER,
)
from .coordinator import GeyserPasteurizationCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]

_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DEVICE_ID): cv.string,
        vol.Optional(ATTR_ENTRY_ID): cv.string,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Geyser Pasteurization from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = GeyserPasteurizationCoordinator(hass, entry)
    await coordinator.async_initialize()
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _async_register_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: GeyserPasteurizationCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown_listeners()

    if not hass.data.get(DOMAIN):
        _async_unregister_services(hass)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


def _get_coordinator_for_call(
    hass: HomeAssistant, call: ServiceCall
) -> GeyserPasteurizationCoordinator:
    """Resolve which config entry's coordinator a service call targets."""
    entries: dict[str, GeyserPasteurizationCoordinator] = hass.data.get(DOMAIN, {})

    device_id = call.data.get(ATTR_DEVICE_ID)
    if device_id:
        device_registry = dr.async_get(hass)
        device = device_registry.async_get(device_id)
        if device is None:
            raise ServiceValidationError(f"Unknown device_id: {device_id}")
        for config_entry_id in device.config_entries:
            if config_entry_id in entries:
                return entries[config_entry_id]
        raise ServiceValidationError(
            f"Device {device_id} is not associated with a Geyser Pasteurization entry"
        )

    entry_id = call.data.get(ATTR_ENTRY_ID)
    if entry_id:
        if entry_id not in entries:
            raise ServiceValidationError(f"Unknown entry_id: {entry_id}")
        return entries[entry_id]

    if len(entries) == 1:
        return next(iter(entries.values()))

    raise ServiceValidationError(
        "Multiple Geyser Pasteurization instances configured; "
        "specify device_id or entry_id to target one"
    )


def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_MANUAL_TRIGGER):
        return

    async def _handle_manual_trigger(call: ServiceCall) -> None:
        coordinator = _get_coordinator_for_call(hass, call)
        await coordinator.async_manual_trigger()

    async def _handle_reset_timer(call: ServiceCall) -> None:
        coordinator = _get_coordinator_for_call(hass, call)
        await coordinator.async_reset_timer()

    async def _handle_cancel_cycle(call: ServiceCall) -> None:
        coordinator = _get_coordinator_for_call(hass, call)
        await coordinator.async_cancel_cycle()

    hass.services.async_register(
        DOMAIN, SERVICE_MANUAL_TRIGGER, _handle_manual_trigger, schema=_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_RESET_TIMER, _handle_reset_timer, schema=_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CANCEL_CYCLE, _handle_cancel_cycle, schema=_SERVICE_SCHEMA
    )


def _async_unregister_services(hass: HomeAssistant) -> None:
    for service in (SERVICE_MANUAL_TRIGGER, SERVICE_RESET_TIMER, SERVICE_CANCEL_CYCLE):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
