"""Config flow for the Geyser Pasteurization integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TimeSelector,
)

from .const import (
    CONF_ALLOWED_END,
    CONF_ALLOWED_START,
    CONF_HEATER_ENTITY,
    CONF_MAX_RUNTIME,
    CONF_REQUIRED_DURATION,
    CONF_ROLLING_WINDOW,
    CONF_STRICT_RESET,
    CONF_TARGET_TEMP,
    CONF_TEMP_SENSOR,
    DEFAULT_MAX_RUNTIME_MINUTES,
    DEFAULT_REQUIRED_DURATION_MINUTES,
    DEFAULT_ROLLING_WINDOW_DAYS,
    DEFAULT_STRICT_RESET,
    DEFAULT_TARGET_TEMP,
    DOMAIN,
    MAX_MAX_RUNTIME_MINUTES,
    MAX_REQUIRED_DURATION_MINUTES,
    MAX_ROLLING_WINDOW_DAYS,
    MAX_TARGET_TEMP,
    MIN_MAX_RUNTIME_MINUTES,
    MIN_REQUIRED_DURATION_MINUTES,
    MIN_ROLLING_WINDOW_DAYS,
    MIN_TARGET_TEMP,
)


def _shared_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Schema for the parameters shared by the config and options flows."""
    return vol.Schema(
        {
            vol.Required(
                CONF_TARGET_TEMP, default=defaults.get(CONF_TARGET_TEMP, DEFAULT_TARGET_TEMP)
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_TARGET_TEMP,
                    max=MAX_TARGET_TEMP,
                    step=0.5,
                    unit_of_measurement="°C",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_REQUIRED_DURATION,
                default=defaults.get(CONF_REQUIRED_DURATION, DEFAULT_REQUIRED_DURATION_MINUTES),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_REQUIRED_DURATION_MINUTES,
                    max=MAX_REQUIRED_DURATION_MINUTES,
                    step=1,
                    unit_of_measurement="min",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_ROLLING_WINDOW,
                default=defaults.get(CONF_ROLLING_WINDOW, DEFAULT_ROLLING_WINDOW_DAYS),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_ROLLING_WINDOW_DAYS,
                    max=MAX_ROLLING_WINDOW_DAYS,
                    step=1,
                    unit_of_measurement="d",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_MAX_RUNTIME,
                default=defaults.get(CONF_MAX_RUNTIME, DEFAULT_MAX_RUNTIME_MINUTES),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_MAX_RUNTIME_MINUTES,
                    max=MAX_MAX_RUNTIME_MINUTES,
                    step=5,
                    unit_of_measurement="min",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                CONF_ALLOWED_START, default=defaults.get(CONF_ALLOWED_START)
            ): TimeSelector(),
            vol.Optional(
                CONF_ALLOWED_END, default=defaults.get(CONF_ALLOWED_END)
            ): TimeSelector(),
            vol.Required(
                CONF_STRICT_RESET,
                default=defaults.get(CONF_STRICT_RESET, DEFAULT_STRICT_RESET),
            ): BooleanSelector(),
        }
    )


class GeyserPasteurizationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Geyser Pasteurization."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step: choose the entities to monitor/control."""
        errors: dict[str, str] = {}

        if user_input is not None:
            unique_id = f"{user_input[CONF_TEMP_SENSOR]}::{user_input[CONF_HEATER_ENTITY]}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            data = {
                CONF_TEMP_SENSOR: user_input[CONF_TEMP_SENSOR],
                CONF_HEATER_ENTITY: user_input[CONF_HEATER_ENTITY],
                CONF_TARGET_TEMP: user_input[CONF_TARGET_TEMP],
                CONF_REQUIRED_DURATION: user_input[CONF_REQUIRED_DURATION],
                CONF_ROLLING_WINDOW: user_input[CONF_ROLLING_WINDOW],
                CONF_MAX_RUNTIME: user_input[CONF_MAX_RUNTIME],
                CONF_ALLOWED_START: user_input.get(CONF_ALLOWED_START),
                CONF_ALLOWED_END: user_input.get(CONF_ALLOWED_END),
                CONF_STRICT_RESET: user_input[CONF_STRICT_RESET],
            }
            return self.async_create_entry(title="Geyser Pasteurization", data=data)

        schema = vol.Schema(
            {
                vol.Required(CONF_TEMP_SENSOR): EntitySelector(
                    EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Required(CONF_HEATER_ENTITY): EntitySelector(
                    EntitySelectorConfig(
                        domain=["switch", "input_boolean", "climate", "water_heater"]
                    )
                ),
            }
        ).extend(_shared_schema({}).schema)

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return GeyserPasteurizationOptionsFlow()


class GeyserPasteurizationOptionsFlow(OptionsFlow):
    """Handle an options flow for Geyser Pasteurization."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        schema = _shared_schema(current)

        return self.async_show_form(step_id="init", data_schema=schema)
