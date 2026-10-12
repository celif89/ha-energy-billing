"""Konfiguracja integracji z poziomu interfejsu HA."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_EXPORT_SENSOR,
    CONF_IMPORT_SENSOR,
    CONF_PRICE_SENSOR,
    DEFAULT_TITLE,
    DOMAIN,
)

SENSORS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IMPORT_SENSOR): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class="energy")
        ),
        vol.Required(CONF_EXPORT_SENSOR): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class="energy")
        ),
        vol.Required(CONF_PRICE_SENSOR): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
    }
)


def _validate(user_input: dict[str, Any]) -> dict[str, str]:
    if user_input[CONF_IMPORT_SENSOR] == user_input[CONF_EXPORT_SENSOR]:
        return {"base": "same_sensor"}
    return {}


class EnergyBillingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> EnergyBillingOptionsFlow:
        return EnergyBillingOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_IMPORT_SENSOR: user_input[CONF_IMPORT_SENSOR],
                    CONF_EXPORT_SENSOR: user_input[CONF_EXPORT_SENSOR],
                }
            )
            errors = _validate(user_input)
            if not errors:
                return self.async_create_entry(title=DEFAULT_TITLE, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                SENSORS_SCHEMA, user_input or {}
            ),
            errors=errors,
        )


class EnergyBillingOptionsFlow(config_entries.OptionsFlow):
    """Zmiana wybranych sensorów bez usuwania integracji."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate(user_input)
            if not errors:
                return self.async_create_entry(data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                SENSORS_SCHEMA, user_input or current
            ),
            errors=errors,
        )
