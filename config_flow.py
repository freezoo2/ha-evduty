"""Config flow for EVduty integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from evdutyfree import EVdutyFree

from homeassistant import config_entries, core
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from . import InvalidAuth, EVdutyCoordinator
from .const import CONF_STATION, CONF_TERMINAL, DOMAIN

COMPONENT_DOMAIN = DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_STATION): str,
        vol.Required(CONF_TERMINAL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(
    hass: core.HomeAssistant, data: dict[str, Any]
) -> dict[str, str]:
    """Validate the user input allows to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    evduty = EVdutyFree(data["username"], data["password"])
    evduty_coordinator = EVdutyCoordinator(data["station"], data["terminal"], evduty, hass)

    await evduty_coordinator.async_validate_input()

    # Return info that you want to store in the config entry.
    return {"title": "EVduty Portal"}


class ConfigFlow(config_entries.ConfigFlow, domain=COMPONENT_DOMAIN):
    """Handle a config flow for EVduty."""

    def __init__(self) -> None:
        """Start the EVduty config flow."""
        self._reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )

        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
            )

        errors = {}

        try:
            await self.async_set_unique_id(user_input["terminal"])
            if not self._reauth_entry:
                self._abort_if_unique_id_configured()
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            if user_input["terminal"] == self._reauth_entry.data[CONF_TERMINAL]:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry, data=user_input, unique_id=user_input["terminal"]
                )
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                )
                return self.async_abort(reason="reauth_successful")
            errors["base"] = "reauth_invalid"
        except ConnectionError:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )